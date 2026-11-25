#!/usr/bin/env python3
"""LLM-as-judge: atribui notas de alinhamento requisito-teste aos pares extraidos do RESTestBench.

O juiz NUNCA recebe os mutantes nem o resultado da execucao. Tres condicoes (RQ2, ablacao):
  completo       -> requisito preciso + spec OpenAPI + teste   (notas: alinhamento, spec, geral)
  sem_requisito  -> spec OpenAPI + teste                       (notas: spec, geral)
  sem_spec       -> requisito preciso + teste                  (notas: alinhamento, geral)
A "nota geral" existe nas tres condicoes e e a que se compara entre elas.

Uso (cada condicao/juiz grava em notas_<condicao>_<modelo>.csv e retoma se interrompido):
  export ANTHROPIC_API_KEY=...
  python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao completo --limite 20
  python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao completo
  python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao sem_requisito
  python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao sem_spec
  # segundo juiz (RQ3): Gemini pela API compativel com OpenAI, subamostra estratificada de 100 pares
  export OPENAI_API_KEY=<chave do Gemini>
  python juiz_llm.py --repo ./RESTestBench --provedor openai --modelo <gemini flash-lite> \
      --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --subamostra 100
  python juiz_llm.py ... --dry-run     # mostra o prompt da 1a linha, sem chamar a API

Raciocinio: --esforco (padrao medium) fixa o nivel nos dois provedores e fica gravado no CSV.
Temperatura: nao e enviada por padrao (o Claude Haiku 5.5 pede que seja omitida); use --temperatura
so com modelos que a aceitem. "--provedor openai" tambem serve para DeepSeek, OpenRouter ou Ollama.
"""
import argparse, csv, json, os, random, re, sys, time
from collections import defaultdict

CONDICOES = {  # quais notas cada condicao pede
    "completo": ["requirement_alignment", "spec_consistency", "overall"],
    "sem_requisito": ["spec_consistency", "overall"],
    "sem_spec": ["requirement_alignment", "overall"],
}
COLUNA = {"requirement_alignment": "alinhamento", "spec_consistency": "consistencia_spec", "overall": "nota_geral"}

INTRO = {
    "completo": "You will assess a pytest test case that was automatically generated to verify ONE "
                "natural-language requirement of a REST API. Judge only from the requirement, the OpenAPI "
                "specification and the test code.",
    "sem_requisito": "You will assess a pytest test case that was automatically generated for a REST API. "
                     "You are NOT given the requirement the test was meant to verify: infer the intended "
                     "behaviour from the test itself. Judge only from the OpenAPI specification and the test code.",
    "sem_spec": "You will assess a pytest test case that was automatically generated to verify ONE "
                "natural-language requirement of a REST API. You are NOT given the API specification: rely on "
                "the requirement, the test code and common REST conventions.",
}
CRITERIO = {
    "requirement_alignment": "requirement_alignment: does the test set up the scenario described in the "
        "requirement and assert the outcome the requirement demands? 1 = unrelated, or no meaningful assertion "
        "on the required behaviour; 3 = exercises the behaviour but asserts it only partially or loosely; "
        "5 = sets up the required scenario and asserts every outcome stated in the requirement.",
    "spec_consistency": "spec_consistency: are endpoints, methods, payloads, authentication, status codes and "
        "response fields consistent with the OpenAPI specification? 1 = several calls or expectations "
        "contradict the spec; 3 = some doubtful assumptions; 5 = fully consistent.",
    "overall": {
        "completo": "overall: how confident are you that this test (a) PASSES on a correct implementation AND "
                    "(b) FAILS on any implementation that violates the requirement? 1 = very unlikely, 5 = very likely.",
        "sem_spec": "overall: how confident are you that this test (a) PASSES on a correct implementation AND "
                    "(b) FAILS on any implementation that violates the requirement? 1 = very unlikely, 5 = very likely.",
        "sem_requisito": "overall: how confident are you that this test (a) PASSES on a correct implementation "
                         "AND (b) FAILS on any implementation that breaks the behaviour the test is meant to "
                         "verify? 1 = very unlikely, 5 = very likely.",
    },
}
PENALIDADE = {
    "completo": "neither stated in the requirement nor guaranteed by the specification",
    "sem_requisito": "not guaranteed by the specification",
    "sem_spec": "not stated in the requirement",
}
# Rubrica v2 (apos o piloto): fatos do ambiente do benchmark, conflito requisito x spec e foco da nota geral.
AMBIENTE = ("Execution environment (a fact of the benchmark): each test runs exactly once against a freshly "
            "reset instance of the service whose database contains only the initial seed data (including any "
            "default admin account). Do not penalise a test for state left by earlier runs, for re-run "
            "conflicts or for relying on data that the initial seed provides.")
CREDENCIAIS = ("Accounts and credentials stated in the requirement exist in the seed data exactly as given; "
               "do not lower any score for relying on them.")
CONFLITO = ("If the requirement demands a response that the specification does not document (for example an "
            "error status code), follow the requirement and do not lower spec_consistency for it.")
FOCO_GERAL = ("For overall, judge whether the test checks the required behaviour; incidental choices (which user "
              "or values are used, extra setup steps) should not lower overall unless they could make the test "
              "fail on a correct implementation or let a faulty one pass.")
CAMPOS_SAIDA = ["id", "condicao", "juiz_provedor", "juiz_modelo", "esforco", "alinhamento", "consistencia_spec",
                "nota_geral", "justificativa", "tokens_entrada", "tokens_cache_leitura",
                "tokens_cache_escrita", "tokens_saida"]


def montar_sistema(condicao, spec):
    dims = CONDICOES[condicao]
    linhas = []
    for i, d in enumerate(dims, 1):
        c = CRITERIO[d][condicao] if isinstance(CRITERIO[d], dict) else CRITERIO[d]
        linhas.append(f"{i}. {c}")
    formato = ", ".join(f'"{d}": <int>' for d in dims)
    txt = (f"You are an expert in REST API testing. {INTRO[condicao]} You cannot run the test.\n\n"
           f"Score the following dimensions on a 1-5 integer scale:\n" + "\n".join(linhas) + "\n\n"
           f"Penalise assertions on behaviour that is {PENALIDADE[condicao]}, because they can make the "
           f"test fail on a correct implementation.\n\n"
           f"{AMBIENTE}" + ("" if condicao == "sem_requisito" else f" {CREDENCIAIS}") + "\n\n" + (f"{CONFLITO}\n\n" if condicao == "completo" else "") + (FOCO_GERAL.replace("the required behaviour", "the behaviour it is meant to verify") if condicao == "sem_requisito" else FOCO_GERAL) + "\n\n"
           f'Answer with a single JSON object and nothing else:\n{{{formato}, "rationale": "<max 60 words>"}}')
    if spec is not None:
        txt += f"\n\nOpenAPI specification of the service under test:\n<spec>\n{spec}\n</spec>"
    return txt


def montar_usuario(condicao, requisito, codigo):
    teste = f'<test language="python">\n{codigo}\n</test>'
    return teste if condicao == "sem_requisito" else f"<requirement>\n{requisito}\n</requirement>\n\n{teste}"


def extrair_json(texto, dims):
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        raise ValueError("resposta sem JSON")
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        # Fallback: aspas nao escapadas na rationale quebram o JSON; as notas sao inteiros e se extraem por regex.
        bruto = m.group(0)
        d = {}
        for k in dims:
            n = re.search(rf'"{k}"\s*:\s*(\d+)', bruto)
            if not n:
                raise
            d[k] = int(n.group(1))
        r = re.search(r'"rationale"\s*:\s*"(.*)"\s*\}\s*$', bruto, re.DOTALL)
        d["rationale"] = r.group(1) if r else ""
    notas = {COLUNA[k]: int(d[k]) for k in dims}
    if not all(1 <= n <= 5 for n in notas.values()):
        raise ValueError(f"nota fora de 1-5: {notas}")
    return notas, str(d.get("rationale", "")).strip()


class Juiz:
    def __init__(self, provedor, modelo, base_url=None, esforco="medium", temperatura=None, max_tokens=4000):
        self.provedor, self.modelo = provedor, modelo
        self.esforco, self.temperatura, self.max_tokens = esforco, temperatura, max_tokens
        if provedor == "anthropic":
            import anthropic
            self.cli = anthropic.Anthropic()
        else:
            import openai
            self.cli = openai.OpenAI(base_url=base_url) if base_url else openai.OpenAI()

    def _chamar(self, sistema, usuario):
        """Devolve (texto, entrada_sem_cache, cache_leitura, cache_escrita, saida)."""
        extra = {} if self.temperatura is None else {"temperature": self.temperatura}
        if self.provedor == "anthropic":
            # O raciocinio adaptativo conta dentro de max_tokens: por isso o limite folgado.
            corpo = {"output_config": {"effort": self.esforco}} if self.esforco else {}
            r = self.cli.messages.create(
                model=self.modelo, max_tokens=self.max_tokens, **extra, extra_body=corpo,
                system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": usuario}])
            texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            if r.stop_reason == "max_tokens" and "{" not in texto:
                raise RuntimeError(f"max_tokens ({self.max_tokens}) esgotado no raciocinio; aumente --max-tokens")
            u = r.usage
            return (texto, u.input_tokens, getattr(u, "cache_read_input_tokens", 0) or 0,
                    getattr(u, "cache_creation_input_tokens", 0) or 0, u.output_tokens)
        corpo = {"reasoning_effort": self.esforco} if self.esforco else {}
        r = self.cli.chat.completions.create(
            model=self.modelo, **extra, extra_body=corpo,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}])
        u = r.usage
        cache = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        return r.choices[0].message.content or "", u.prompt_tokens - cache, cache, 0, u.completion_tokens

    def avaliar(self, sistema, usuario, dims, tentativas=4):
        for i in range(tentativas):
            try:
                texto, *tokens = self._chamar(sistema, usuario)
                notas, just = extrair_json(texto, dims)
                return notas, just, tokens
            except Exception as e:  # erro de API, limite de taxa ou JSON invalido
                msg = str(e).lower()
                if "temperature" in msg and self.temperatura is not None:
                    print("  aviso: o modelo nao aceita 'temperature'; seguindo sem o parametro.")
                    self.temperatura = None
                    continue
                if self.esforco and any(p in msg for p in ("effort", "output_config", "reasoning")):
                    print(f"  aviso: o modelo nao aceita o nivel de esforco '{self.esforco}'; "
                          "seguindo com o padrao do modelo (gravado como 'padrao' no CSV).")
                    self.esforco = None
                    continue
                espera = 2 ** (i + 1)
                print(f"  tentativa {i + 1} falhou ({type(e).__name__}: {str(e)[:120]}); nova tentativa em {espera}s")
                time.sleep(espera)
        return None


def subamostra_estratificada(linhas, n, seed):
    grupos = defaultdict(list)
    for l in linhas:
        grupos[l["categoria"]].append(l)
    cats, rnd, escolhidas = sorted(grupos), random.Random(seed), []
    for i, c in enumerate(cats):
        k = n // len(cats) + (1 if i < n % len(cats) else 0)
        g = sorted(grupos[c], key=lambda l: int(l["id"]))
        escolhidas += rnd.sample(g, min(k, len(g)))
    return escolhidas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="clone do RESTestBench (para ler as specs)")
    ap.add_argument("--entrada", default="amostra_restestbench.csv")
    ap.add_argument("--saida", default=None, help="padrao: notas_<condicao>_<modelo>.csv")
    ap.add_argument("--condicao", choices=list(CONDICOES), default="completo")
    ap.add_argument("--provedor", choices=["anthropic", "openai"], default="anthropic")
    ap.add_argument("--modelo", required=True, help="ex.: claude-haiku-5-5")
    ap.add_argument("--base-url", default=None, help="endpoint compativel com OpenAI (opcional)")
    ap.add_argument("--esforco", choices=["low", "medium", "high", "padrao"], default="medium",
                    help="nivel de raciocinio (Anthropic: effort; OpenAI/Gemini: reasoning_effort). "
                         "'padrao' nao envia o parametro")
    ap.add_argument("--temperatura", type=float, default=None, help="so para modelos que aceitam (padrao: omitida)")
    ap.add_argument("--max-tokens", type=int, default=4000, help="Anthropic: limite de saida, raciocinio incluso")
    ap.add_argument("--subamostra", type=int, default=0, help="avaliar so N pares, estratificados por categoria")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limite", type=int, default=0, help="parar apos N pares (piloto)")
    ap.add_argument("--pausa", type=float, default=0.0, help="segundos entre chamadas")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    saida = a.saida or f"notas_{a.condicao}_{re.sub(r'[^A-Za-z0-9.-]+', '-', a.modelo)}.csv"

    csv.field_size_limit(sys.maxsize)
    with open(a.entrada, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if a.subamostra:
        linhas = subamostra_estratificada(linhas, a.subamostra, a.seed)
    linhas.sort(key=lambda l: (l["servico"], int(l["id"])))  # agrupa por servico para aproveitar o cache

    feitos = set()
    if os.path.exists(saida):
        with open(saida, encoding="utf-8") as f:
            feitos = {r["id"] for r in csv.DictReader(f)}
    pendentes = [l for l in linhas if l["id"] not in feitos]
    if a.limite:
        pendentes = pendentes[:a.limite]
    print(f"Condicao {a.condicao} | {len(linhas)} pares, {len(feitos)} ja avaliados, "
          f"{len(pendentes)} a avaliar agora -> {saida}")
    if not pendentes:
        return

    specs = {}
    def sistema_de(servico):
        if servico not in specs:
            spec = None
            if a.condicao != "sem_spec":
                with open(os.path.join(a.repo, "services", servico, "spec.json"), encoding="utf-8") as f:
                    spec = json.dumps(json.load(f), separators=(",", ":"))  # compacta para gastar menos tokens
            specs[servico] = montar_sistema(a.condicao, spec)
        return specs[servico]

    def usuario_de(l):
        return montar_usuario(a.condicao, l["requisito_preciso"], l["codigo_teste"])

    if a.dry_run:
        l = pendentes[0]
        print("=== SISTEMA (spec truncada) ===\n" + sistema_de(l["servico"])[:3500] + "\n...")
        print("=== USUARIO ===\n" + usuario_de(l))
        return

    esforco = None if a.esforco == "padrao" else a.esforco
    juiz = Juiz(a.provedor, a.modelo, a.base_url, esforco=esforco, temperatura=a.temperatura,
                max_tokens=a.max_tokens)
    dims = CONDICOES[a.condicao]
    novo, falhas = not os.path.exists(saida), 0
    with open(saida, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_SAIDA)
        if novo:
            w.writeheader()
        for i, l in enumerate(pendentes, 1):
            res = juiz.avaliar(sistema_de(l["servico"]), usuario_de(l), dims)
            if res is None:
                falhas += 1
                print(f"[{i}/{len(pendentes)}] id={l['id']}: sem resposta valida, pulando")
                continue
            notas, just, (t_in, t_cl, t_ce, t_out) = res
            w.writerow({"id": l["id"], "condicao": a.condicao, "juiz_provedor": a.provedor,
                        "juiz_modelo": a.modelo, "esforco": juiz.esforco or "padrao", **notas,
                        "justificativa": just, "tokens_entrada": t_in,
                        "tokens_cache_leitura": t_cl, "tokens_cache_escrita": t_ce, "tokens_saida": t_out})
            f.flush()
            print(f"[{i}/{len(pendentes)}] id={l['id']} {l['servico']}: {notas} (cache={t_cl})")
            if a.pausa:
                time.sleep(a.pausa)
    print(f"Concluido. Falhas: {falhas}. Rode de novo para tentar as que falharam.")


if __name__ == "__main__":
    main()
