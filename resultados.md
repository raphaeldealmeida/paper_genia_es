Amostra: 300 pares
Notas por condicao e juiz: {'completo/claude-haiku-5-5': 300, 'completo/gemini-3.5-flash-lite': 100, 'sem_requisito/claude-haiku-5-5': 300, 'sem_spec/claude-haiku-5-5': 300}
Juiz principal: claude-haiku-5-5

# RQ1 - Validade do juiz (condicao completo)

## T1. Media (dp) das notas por categoria

| Nota | incorreto (n=100) | fraco (n=100) | efetivo (n=100) |
|---|---|---|---|
| Alinhamento | 2.57 (1.44) | 2.94 (1.14) | 4.50 (0.93) |
| Consist. spec | 3.18 (1.15) | 4.40 (0.57) | 4.68 (0.51) |
| Nota geral | 2.03 (1.23) | 2.81 (1.07) | 4.29 (0.84) |

## T2. AUC por contraste, IC 95% (0,5 = acaso; 1,0 = separacao perfeita)

| Contraste | n+ / n- | Alinhamento | Consist. spec | Nota geral |
|---|---|---|---|---|
| efetivo vs. resto | 100 / 200 | 0.840 [0.79, 0.88] | 0.742 [0.69, 0.79] | 0.874 [0.84, 0.91] |
| passa vs. incorreto | 200 / 100 | 0.722 [0.67, 0.78] | 0.828 [0.77, 0.88] | 0.805 [0.75, 0.85] |
| efetivo vs. fraco | 100 / 100 | 0.828 [0.77, 0.88] | 0.630 [0.56, 0.70] | 0.841 [0.79, 0.89] |
| Spearman com MS_phi* | 300 | 0.543 [0.45, 0.63] | 0.572 [0.48, 0.65] | 0.647 [0.57, 0.72] |

*Secundario: a amostra e estratificada (100 por categoria), o que afeta rho mas nao a AUC.

# RQ2 - Papel do requisito em NL (nota geral, pares avaliados nas condicoes)

## T3. AUC por condicao e baseline (IC 95%)

| Pontuador | n | efetivo vs. resto | passa vs. incorreto | efetivo vs. fraco |
|---|---|---|---|---|
| completo | 300 | 0.874 [0.83, 0.91] | 0.805 [0.75, 0.85] | 0.841 [0.78, 0.89] |
| sem_requisito | 300 | 0.679 [0.62, 0.74] | 0.808 [0.75, 0.86] | 0.549 [0.47, 0.62] |
| sem_spec | 300 | 0.782 [0.73, 0.83] | 0.740 [0.68, 0.80] | 0.751 [0.69, 0.81] |
| baseline: n de asserts | 300 | 0.567 [0.50, 0.63] | 0.579 [0.51, 0.65] | 0.536 [0.46, 0.62] |

## T4. Diferenca pareada de AUC: completo - outro (IC 95%; * = IC exclui zero)

| Comparacao | n | efetivo vs. resto | passa vs. incorreto | efetivo vs. fraco |
|---|---|---|---|---|
| completo - sem_requisito | 300 | +0.195 [+0.13, +0.26]* | -0.003 [-0.06, +0.05] | +0.292 [+0.21, +0.38]* |
| completo - sem_spec | 300 | +0.092 [+0.05, +0.13]* | +0.064 [+0.02, +0.11]* | +0.090 [+0.04, +0.14]* |
| completo - n_asserts | 300 | +0.308 [+0.23, +0.39]* | +0.225 [+0.15, +0.31]* | +0.304 [+0.20, +0.41]* |

# RQ3 - Custo e estabilidade

## T5. Tokens por par (mediana) e custo

| Condicao / juiz | n | entrada | cache (leitura) | saida | US$ por par (mediana) | US$ total | custo de gerar o teste (mediana) |
|---|---|---|---|---|---|---|---|
| completo / claude-haiku-5-5 | 300 | 1041 | 8557 | 498 | 0.00043 (0.1x o custo de gerar) | 0.13 | 0.00489 |
| completo / gemini-3.5-flash-lite | 100 | 5514 | 0 | 84 | 0.00186 (0.5x o custo de gerar) | 0.17 | 0.00400 |
| sem_requisito / claude-haiku-5-5 | 300 | 892 | 8362 | 548 | 0.00045 (0.1x o custo de gerar) | 0.14 | 0.00489 |
| sem_spec / claude-haiku-5-5 | 300 | 1041 | 602 | 432 | 0.00033 (0.1x o custo de gerar) | 0.10 | 0.00489 |

## T6. Concordancia entre juizes (condicao completo, mesmos pares)

| Juiz secundario | n | Nota | kappa quadratico | concordancia exata | dif. <= 1 | AUC efetivo vs. resto (principal / secundario) |
|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 100 | Alinhamento | 0.899 | 66% | 96% | 0.842 / 0.791 |
| gemini-3.5-flash-lite | 100 | Consist. spec | 0.573 | 49% | 87% | 0.798 / 0.644 |
| gemini-3.5-flash-lite | 100 | Nota geral | 0.817 | 55% | 92% | 0.876 / 0.814 |

## T7. (Suplementar) AUC efetivo vs. resto da nota geral, por subgrupo (n pequeno: cautela)

| Subgrupo | n | AUC |
|---|---|---|
| variante = precise | 128 | 0.797 |
| variante = vague | 172 | 0.833 |
| servico = fastapi | 199 | 0.899 |
| servico = nestjs-realworld | 68 | 0.874 |
| servico = todoapp | 33 | 0.645 |

Figura gravada em auc_condicoes.pdf
CSV combinado (condicao completo, juiz principal) gravado em combinado.csv
