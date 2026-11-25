"""Repetibilidade do juiz principal: compara duas passagens do mesmo juiz nos mesmos pares.

Uso:
  python repetibilidade.py                     # padrao: notas_completo_claude-haiku-5-5.csv x repeticao_completo_claude-haiku-5-5.csv
  python repetibilidade.py --original A.csv --repeticao B.csv --preco 0.10,0.01,0.125,0.50
"""
import argparse, csv, sys

import pandas as pd
from scipy.stats import mannwhitneyu

from analisar import kappa_quadratico

NOTAS = [("nota_geral", "Nota geral"), ("alinhamento", "Alinhamento"), ("consistencia_spec", "Consist. spec")]


def auc(pos, neg):
    return mannwhitneyu(pos, neg).statistic / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amostra", default="amostra_restestbench.csv")
    ap.add_argument("--original", default="notas_completo_claude-haiku-5-5.csv")
    ap.add_argument("--repeticao", default="repeticao_completo_claude-haiku-5-5.csv")
    ap.add_argument("--preco", default="0.10,0.01,0.125,0.50",
                    help="US$/milhao de tokens: entrada,cache_leitura,cache_escrita,saida (custo da repeticao)")
    a = ap.parse_args()

    csv.field_size_limit(sys.maxsize)
    org, rep = pd.read_csv(a.original), pd.read_csv(a.repeticao)
    cat = pd.read_csv(a.amostra, usecols=["id", "categoria"])
    m = rep.merge(org, on="id", suffixes=("_r", "_o")).merge(cat, on="id")

    print(f"# Repetibilidade do juiz ({len(m)} pares avaliados nas duas passagens)\n")
    print("| Nota | kappa quadratico | concordancia exata | dif. <= 1 |")
    print("|---|---|---|---|")
    for col, nome in NOTAS:
        x, y = m[col + "_o"], m[col + "_r"]
        if x.isna().all() or y.isna().all():
            continue
        print(f"| {nome} | {kappa_quadratico(x, y):.3f} | {(x == y).mean():.0%} | {((x - y).abs() <= 1).mean():.0%} |")

    efetivo = m["categoria"] == "efetivo"
    a1 = auc(m["nota_geral_o"][efetivo], m["nota_geral_o"][~efetivo])
    a2 = auc(m["nota_geral_r"][efetivo], m["nota_geral_r"][~efetivo])
    print(f"\nAUC efetivo vs. resto (nota geral): 1a passagem {a1:.3f} | 2a passagem {a2:.3f}")

    e, cl, ce, s = (float(v) for v in a.preco.split(","))
    custo = (rep.tokens_entrada * e + rep.tokens_cache_leitura * cl + rep.tokens_cache_escrita * ce
             + rep.tokens_saida * s).sum() / 1e6
    print(f"Custo da repeticao: US$ {custo:.3f}")


if __name__ == "__main__":
    main()
