#!/usr/bin/env python3
"""Extrai triplas (requisito NL, teste gerado, MS_phi) dos resultados publicados do RESTestBench.

Nao gera testes nem executa Docker: usa os testes e os resultados de mutacao que ja estao
em results/runs/ do repositorio (https://github.com/casablancahotelsoftware/RESTestBench).

Exemplos:
  python extrair_amostra.py --repo ./RESTestBench
  python extrair_amostra.py --repo ./RESTestBench --por-categoria 100 --seed 42
  python extrair_amostra.py --repo ./RESTestBench --servicos fastapi --modelos gpt5nano sonnet45

Categorias (desfecho do teste na implementacao valida e nos mutantes do requisito):
  incorreto -> falha na implementacao valida (o benchmark atribui MS_phi = 0)
  fraco     -> passa na valida, mas deixa mutante(s) sobreviver
  efetivo   -> passa na valida e mata todos os mutantes

Colunas auxiliares:
  n_asserts          -> baseline trivial (RQ2): numero de verificacoes no teste
  custo_geracao_usd  -> custo de gerar o teste, do manifesto do benchmark (RQ3)
"""
import argparse, ast, csv, glob, json, os, random, re
from collections import Counter, defaultdict


def carregar_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def contar_asserts(codigo):
    """Conta comandos assert, chamadas assert*/assert_* e pytest.raises; usa regex se o codigo nao compilar."""
    try:
        arvore = ast.parse(codigo)
    except SyntaxError:
        return len(re.findall(r"\bassert\w*", codigo))
    n = 0
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assert):
            n += 1
        elif isinstance(no, ast.Call):
            f = no.func
            nome = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if nome.lower().startswith("assert") or nome == "raises":
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="pasta do clone do RESTestBench")
    ap.add_argument("--execucao", default="results_1", help="results_1, results_2 ou results_3")
    ap.add_argument("--servicos", nargs="+", default=["fastapi", "nestjs-realworld", "todoapp"])
    ap.add_argument("--abordagens", nargs="+", default=["zero-shot"], help="zero-shot e/ou refinement")
    ap.add_argument("--variantes", nargs="+", default=["precise", "vague"])
    ap.add_argument("--modelos", nargs="*", default=None, help="ex.: gpt5nano sonnet45 (padrao: todos)")
    ap.add_argument("--por-categoria", type=int, default=0, help="amostra estratificada: N por categoria (0 = tudo)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="amostra_restestbench.csv")
    a = ap.parse_args()

    # Requisitos (texto preciso e vago) indexados por (servico, id)
    reqs = {}
    for s in a.servicos:
        for f in glob.glob(os.path.join(a.repo, "data", "requirements", s, "requirement_*.json")):
            r = carregar_json(f)
            reqs[(s, r["id"])] = r

    # Execucoes: se houver duplicatas da mesma configuracao, fica a mais recente
    execucoes = {}
    padrao = os.path.join(a.repo, "results", "runs", a.execucao, "**", "evaluation_results.json")
    for f in glob.glob(padrao, recursive=True):
        pasta = os.path.dirname(f)
        cfg = carregar_json(os.path.join(pasta, "config.json"))
        modelo, abordagem = cfg["tool_name"].split("_", 1)
        variante = "precise" if cfg["use_precise"] else "vague"
        if (cfg["service"] not in a.servicos or abordagem not in a.abordagens or variante not in a.variantes
                or (a.modelos and modelo not in a.modelos)):
            continue
        chave = (modelo, abordagem, cfg["service"], variante)
        if chave not in execucoes or cfg["timestamp"] > execucoes[chave][0]["timestamp"]:
            execucoes[chave] = (cfg, pasta, f)

    linhas = []
    for (modelo, abordagem, servico, variante), (cfg, pasta, f) in sorted(execucoes.items()):
        manifesto = os.path.join(pasta, "generation_manifest.json")
        custos = {}
        if os.path.exists(manifesto):
            custos = {t["requirement_id"]: t.get("generation_cost") for t in carregar_json(manifesto)["tests"]
                      if t.get("mode") == "valid"}
        for r in carregar_json(f)["requirements"]:
            vt, n, rid = r["valid_test"], r["num_mutants"], r["requirement_id"]
            teste = os.path.join(pasta, "generated_tests", f"req_{rid}", "test.py")
            if not os.path.exists(teste) or (servico, rid) not in reqs:
                continue
            req = reqs[(servico, rid)]
            mortos, passa = len(vt["mutants_killed"]), bool(vt["passes_on_valid"])
            cat = "incorreto" if not passa else ("efetivo" if mortos == n else "fraco")
            with open(teste, encoding="utf-8") as t:
                codigo = t.read()
            linhas.append({
                "execucao": a.execucao, "modelo": modelo, "abordagem": abordagem, "servico": servico,
                "variante": variante, "req_id": rid,
                "requisito_usado": req["requirement_precise"] if variante == "precise" else req["requirement_vague"],
                "requisito_preciso": req["requirement_precise"], "requisito_vago": req["requirement_vague"],
                "codigo_teste": codigo, "passa_na_valida": int(passa), "n_mutantes": n,
                "mutantes_mortos": mortos, "ms_phi": round(mortos / n, 4) if passa else 0.0,
                "categoria": cat, "n_asserts": contar_asserts(codigo),
                "custo_geracao_usd": custos.get(rid),
                "spec_path": os.path.relpath(os.path.join(a.repo, "services", servico, "spec.json"), a.repo),
                "test_path": os.path.relpath(teste, a.repo),
            })

    if a.por_categoria > 0:
        rnd, grupos = random.Random(a.seed), defaultdict(list)
        for l in linhas:
            grupos[l["categoria"]].append(l)
        linhas = [l for g in sorted(grupos) for l in rnd.sample(grupos[g], min(a.por_categoria, len(grupos[g])))]

    for i, l in enumerate(linhas, 1):
        l["id"] = i
    campos = ["id"] + [c for c in (linhas[0] if linhas else {}) if c != "id"]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    print(f"{len(linhas)} linhas gravadas em {a.out}")
    print("Por categoria:", dict(Counter(l["categoria"] for l in linhas)))
    print("Por servico:  ", dict(Counter(l["servico"] for l in linhas)))
    print("Por modelo:   ", dict(Counter(l["modelo"] for l in linhas)))


if __name__ == "__main__":
    main()
