#!/usr/bin/env python3
"""Analise do estudo: as notas do LLM juiz acompanham o MS_phi do RESTestBench?

Uso:
  python analisar.py --amostra amostra_restestbench.csv --notas "notas_*.csv"
  python analisar.py ... --excluir-modelos sonnet45          # sensibilidade a autopreferencia
  python analisar.py ... --preco claude-haiku-5-5=E,CL,CE,S  # US$/milhao de tokens: entrada,
                                                             # leitura de cache, escrita de cache, saida
Tabelas (Markdown) e figura:
  RQ1 validade      T1 media (dp) das notas por categoria | T2 AUC por contraste (principal) e Spearman
  RQ2 requisito     T3 AUC da nota geral por condicao e do baseline n_asserts | T4 diferenca pareada de AUC
  RQ3 custo/estab.  T5 tokens e custo por par x custo de geracao | T6 concordancia entre juizes
  Suplementar       T7 AUC (efetivo vs. resto) por variante e servico
  Figura            AUC por condicao com IC 95% (--figura)
"""
import argparse, glob
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

NOTAS = {"alinhamento": "Alinhamento", "consistencia_spec": "Consist. spec", "nota_geral": "Nota geral"}
CONTRASTES = {  # (positivos, negativos); categorias fora dos dois grupos ficam de fora
    "efetivo vs. resto": (["efetivo"], ["fraco", "incorreto"]),
    "passa vs. incorreto": (["efetivo", "fraco"], ["incorreto"]),
    "efetivo vs. fraco": (["efetivo"], ["fraco"]),
}
CONDICOES = ["completo", "sem_requisito", "sem_spec"]


def auc(pos, neg):
    """P(nota de um positivo > nota de um negativo); empates contam 0,5 (Mann-Whitney)."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    r = rankdata(np.concatenate([pos, neg]))
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def separar(df, col, contraste):
    p, n = CONTRASTES[contraste]
    return df[df.categoria.isin(p)][col].to_numpy(float), df[df.categoria.isin(n)][col].to_numpy(float)


def ic_auc(pos, neg, B, rng):
    v = [auc(pos[rng.integers(0, len(pos), len(pos))], neg[rng.integers(0, len(neg), len(neg))]) for _ in range(B)]
    return np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5)


def delta_pareado(df, col_a, col_b, contraste, B, rng):
    """AUC(a) - AUC(b) nos mesmos pares, com IC 95% por bootstrap pareado e estratificado."""
    p, n = CONTRASTES[contraste]
    P, N = df[df.categoria.isin(p)], df[df.categoria.isin(n)]
    pa, pb, na, nb = (P[col_a].to_numpy(float), P[col_b].to_numpy(float),
                      N[col_a].to_numpy(float), N[col_b].to_numpy(float))
    d = auc(pa, na) - auc(pb, nb)
    v = []
    for _ in range(B):
        i, j = rng.integers(0, len(P), len(P)), rng.integers(0, len(N), len(N))
        v.append(auc(pa[i], na[j]) - auc(pb[i], nb[j]))
    return d, np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5), len(P), len(N)


def kappa_quadratico(a, b, k=5):
    a, b = np.asarray(a, int) - 1, np.asarray(b, int) - 1
    O = np.zeros((k, k))
    for x, y in zip(a, b):
        O[x, y] += 1
    O /= O.sum()
    E = np.outer(O.sum(1), O.sum(0))
    W = (np.subtract.outer(np.arange(k), np.arange(k)) ** 2) / (k - 1) ** 2
    return 1 - (W * O).sum() / (W * E).sum()


def fmt(v, lo=None, hi=None):
    return "–" if np.isnan(v) else (f"{v:.3f}" if lo is None else f"{v:.3f} [{lo:.2f}, {hi:.2f}]")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amostra", default="amostra_restestbench.csv")
    ap.add_argument("--notas", nargs="+", default=["notas_*.csv"], help="arquivos (aceita curinga entre aspas)")
    ap.add_argument("--juiz-principal", default=None, help="padrao: o juiz com mais notas na condicao completo")
    ap.add_argument("--excluir-modelos", nargs="*", default=[], help="modelos geradores a excluir")
    ap.add_argument("--preco", nargs="*", default=[], help="MODELO=entrada,cache_leitura,cache_escrita,saida")
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--figura", default="auc_condicoes.pdf")
    ap.add_argument("--saida", default="combinado.csv")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    amostra = pd.read_csv(a.amostra)
    amostra = amostra[~amostra.modelo.isin(a.excluir_modelos)]
    arquivos = sorted({f for padrao in a.notas for f in glob.glob(padrao)})
    if not arquivos:
        raise SystemExit("Nenhum arquivo de notas encontrado.")
    notas = pd.concat([pd.read_csv(f) for f in arquivos], ignore_index=True)
    notas = notas[notas.id.isin(amostra.id)]
    contagem = notas.groupby(["condicao", "juiz_modelo"]).size()
    juiz = a.juiz_principal or contagem.loc["completo"].idxmax()
    print(f"Amostra: {len(amostra)} pares" + (f" (excluidos: {', '.join(a.excluir_modelos)})" if a.excluir_modelos else ""))
    print("Notas por condicao e juiz:", {f"{c}/{j}": int(n) for (c, j), n in contagem.items()})
    print(f"Juiz principal: {juiz}\n")

    def notas_de(condicao, j=juiz):
        sel = notas[(notas.condicao == condicao) & (notas.juiz_modelo == j)].drop_duplicates("id", keep="last")
        return amostra.merge(sel, on="id", how="inner")

    base = notas_de("completo")
    base.to_csv(a.saida, index=False)

    # ---------------- RQ1 ----------------
    print("# RQ1 - Validade do juiz (condicao completo)\n")
    print("## T1. Media (dp) das notas por categoria\n")
    cats = [c for c in ["incorreto", "fraco", "efetivo"] if c in set(base.categoria)]
    print("| Nota | " + " | ".join(f"{c} (n={int((base.categoria == c).sum())})" for c in cats) + " |")
    print("|---|" + "---|" * len(cats))
    for col, nome in NOTAS.items():
        cel = [f"{base[base.categoria == c][col].mean():.2f} ({base[base.categoria == c][col].std():.2f})" for c in cats]
        print(f"| {nome} | " + " | ".join(cel) + " |")

    print("\n## T2. AUC por contraste, IC 95% (0,5 = acaso; 1,0 = separacao perfeita)\n")
    print("| Contraste | n+ / n- | " + " | ".join(NOTAS.values()) + " |\n|---|---|" + "---|" * len(NOTAS))
    for c in CONTRASTES:
        cel = []
        for col in NOTAS:
            p, n = separar(base, col, c)
            cel.append(fmt(auc(p, n), *ic_auc(p, n, a.bootstrap, rng)))
        p, n = separar(base, "nota_geral", c)
        print(f"| {c} | {len(p)} / {len(n)} | " + " | ".join(cel) + " |")
    y = base.ms_phi.to_numpy(float)
    rhos = []
    for col in NOTAS:
        x = base[col].to_numpy(float)
        v = [spearmanr(x[i], y[i]).statistic for i in (rng.integers(0, len(x), len(x)) for _ in range(a.bootstrap))]
        rhos.append(fmt(spearmanr(x, y).statistic, np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5)))
    print(f"| Spearman com MS_phi* | {len(base)} | " + " | ".join(rhos) + " |")
    print("\n*Secundario: a amostra e estratificada (100 por categoria), o que afeta rho mas nao a AUC.")

    # ---------------- RQ2 ----------------
    print("\n# RQ2 - Papel do requisito em NL (nota geral, pares avaliados nas condicoes)\n")
    comb = amostra[["id", "categoria", "n_asserts"]].copy()
    for cond in CONDICOES:
        d = notas_de(cond)
        if len(d):
            comb = comb.merge(d[["id", "nota_geral"]].rename(columns={"nota_geral": cond}), on="id", how="left")
    pontuadores = [c for c in CONDICOES if c in comb] + ["n_asserts"]
    print("## T3. AUC por condicao e baseline (IC 95%)\n")
    print("| Pontuador | n | " + " | ".join(CONTRASTES) + " |\n|---|---|" + "---|" * len(CONTRASTES))
    resultados_fig = {}
    for s in pontuadores:
        d = comb.dropna(subset=[s])
        cel, resultados_fig[s] = [], []
        for c in CONTRASTES:
            p, n = separar(d, s, c)
            v, (lo, hi) = auc(p, n), ic_auc(p, n, a.bootstrap, rng)
            cel.append(fmt(v, lo, hi))
            resultados_fig[s].append((v, lo, hi))
        rotulo = "baseline: n de asserts" if s == "n_asserts" else s
        print(f"| {rotulo} | {len(d)} | " + " | ".join(cel) + " |")

    outros = [s for s in pontuadores if s != "completo"]
    if "completo" in comb and outros:
        print("\n## T4. Diferenca pareada de AUC: completo - outro (IC 95%; * = IC exclui zero)\n")
        print("| Comparacao | n | " + " | ".join(CONTRASTES) + " |\n|---|---|" + "---|" * len(CONTRASTES))
        for s in outros:
            d = comb.dropna(subset=["completo", s])
            cel = []
            for c in CONTRASTES:
                dv, lo, hi, _, _ = delta_pareado(d, "completo", s, c, a.bootstrap, rng)
                cel.append(f"{dv:+.3f} [{lo:+.2f}, {hi:+.2f}]{'*' if lo > 0 or hi < 0 else ''}")
            print(f"| completo - {s} | {len(d)} | " + " | ".join(cel) + " |")

    # ---------------- RQ3 ----------------
    print("\n# RQ3 - Custo e estabilidade\n")
    precos = {}
    for p in a.preco:
        m, v = p.split("=")
        precos[m] = [float(x) for x in v.split(",")]
    print("## T5. Tokens por par (mediana) e custo\n")
    print("| Condicao / juiz | n | entrada | cache (leitura) | saida | US$ por par (mediana) | US$ total | "
          "custo de gerar o teste (mediana) |\n|---|---|---|---|---|---|---|---|")
    for (cond, j), g in notas.groupby(["condicao", "juiz_modelo"]):
        g = g.drop_duplicates("id", keep="last").merge(amostra[["id", "custo_geracao_usd"]], on="id")
        custo, total = "informe --preco", "–"
        if j in precos:
            e, cl, ce, s = precos[j]
            c = (g.tokens_entrada * e + g.tokens_cache_leitura * cl + g.tokens_cache_escrita * ce
                 + g.tokens_saida * s) / 1e6
            razao = c.median() / g.custo_geracao_usd.median()
            custo, total = f"{c.median():.5f} ({razao:.1f}x o custo de gerar)", f"{c.sum():.2f}"
        print(f"| {cond} / {j} | {len(g)} | {g.tokens_entrada.median():.0f} | {g.tokens_cache_leitura.median():.0f} "
              f"| {g.tokens_saida.median():.0f} | {custo} | {total} | {g.custo_geracao_usd.median():.5f} |")

    secundarios = [j for j in contagem.loc["completo"].index if j != juiz]
    print("\n## T6. Concordancia entre juizes (condicao completo, mesmos pares)\n")
    if not secundarios:
        print("Sem segundo juiz na condicao completo.")
    else:
        print("| Juiz secundario | n | Nota | kappa quadratico | concordancia exata | dif. <= 1 | "
              "AUC efetivo vs. resto (principal / secundario) |\n|---|---|---|---|---|---|---|")
        for j in secundarios:
            d = base.merge(notas_de("completo", j)[["id"] + list(NOTAS)], on="id", suffixes=("", "_2"))
            for col, nome in NOTAS.items():
                x, z = d[col].to_numpy(int), d[col + "_2"].to_numpy(int)
                p1, n1 = separar(d, col, "efetivo vs. resto")
                p2, n2 = separar(d, col + "_2", "efetivo vs. resto")
                print(f"| {j} | {len(d)} | {nome} | {kappa_quadratico(x, z):.3f} | {np.mean(x == z):.0%} | "
                      f"{np.mean(abs(x - z) <= 1):.0%} | {auc(p1, n1):.3f} / {auc(p2, n2):.3f} |")

    # ---------------- Suplementar ----------------
    print("\n## T7. (Suplementar) AUC efetivo vs. resto da nota geral, por subgrupo (n pequeno: cautela)\n")
    print("| Subgrupo | n | AUC |\n|---|---|---|")
    for grupo in ["variante", "servico"]:
        for valor, g in base.groupby(grupo):
            p, n = separar(g, "nota_geral", "efetivo vs. resto")
            print(f"| {grupo} = {valor} | {len(g)} | {fmt(auc(p, n))} |")

    # ---------------- Figura ----------------
    if a.figura:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 3.2))
        largura, xs = 0.8 / len(resultados_fig), np.arange(len(CONTRASTES))
        for k, (s, vals) in enumerate(resultados_fig.items()):
            v = np.array([x[0] for x in vals])
            err = np.array([[x[0] - x[1] for x in vals], [x[2] - x[0] for x in vals]])
            ax.bar(xs + k * largura - 0.4 + largura / 2, v, largura, yerr=err, capsize=3,
                   label="n de asserts" if s == "n_asserts" else s.replace("_", " "))
        ax.axhline(0.5, color="gray", lw=0.8, ls="--")
        ax.set_xticks(xs, list(CONTRASTES))
        ax.set_ylabel("AUC")
        ax.set_ylim(0, 1)
        ax.legend(fontsize=8, ncol=len(resultados_fig), loc="upper center", bbox_to_anchor=(0.5, 1.18), frameon=False)
        fig.tight_layout()
        fig.savefig(a.figura, bbox_inches="tight")
        print(f"\nFigura gravada em {a.figura}")
    print(f"CSV combinado (condicao completo, juiz principal) gravado em {a.saida}")


if __name__ == "__main__":
    main()
