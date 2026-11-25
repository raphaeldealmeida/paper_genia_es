Amostra: 266 pares (excluidos: sonnet45)
Notas por condicao e juiz: {'completo/claude-haiku-5-5': 266, 'completo/gemini-3.5-flash-lite': 91, 'sem_requisito/claude-haiku-5-5': 266, 'sem_spec/claude-haiku-5-5': 266}
Juiz principal: claude-haiku-5-5

# RQ1 - Validade do juiz (condicao completo)

## T1. Media (dp) das notas por categoria

| Nota | incorreto (n=96) | fraco (n=85) | efetivo (n=85) |
|---|---|---|---|
| Alinhamento | 2.59 (1.47) | 2.94 (1.13) | 4.52 (0.89) |
| Consist. spec | 3.19 (1.17) | 4.41 (0.56) | 4.73 (0.50) |
| Nota geral | 2.07 (1.23) | 2.81 (1.04) | 4.33 (0.84) |

## T2. AUC por contraste, IC 95% (0,5 = acaso; 1,0 = separacao perfeita)

| Contraste | n+ / n- | Alinhamento | Consist. spec | Nota geral |
|---|---|---|---|---|
| efetivo vs. resto | 85 / 181 | 0.843 [0.79, 0.89] | 0.761 [0.71, 0.81] | 0.881 [0.84, 0.92] |
| passa vs. incorreto | 170 / 96 | 0.718 [0.65, 0.78] | 0.827 [0.77, 0.88] | 0.801 [0.74, 0.85] |
| efetivo vs. fraco | 85 / 85 | 0.836 [0.78, 0.89] | 0.651 [0.58, 0.72] | 0.851 [0.79, 0.91] |
| Spearman com MS_phi* | 266 | 0.533 [0.43, 0.62] | 0.594 [0.50, 0.68] | 0.644 [0.56, 0.72] |

*Secundario: a amostra e estratificada (100 por categoria), o que afeta rho mas nao a AUC.

# RQ2 - Papel do requisito em NL (nota geral, pares avaliados nas condicoes)

## T3. AUC por condicao e baseline (IC 95%)

| Pontuador | n | efetivo vs. resto | passa vs. incorreto | efetivo vs. fraco |
|---|---|---|---|---|
| completo | 266 | 0.881 [0.84, 0.92] | 0.801 [0.74, 0.85] | 0.851 [0.79, 0.90] |
| sem_requisito | 266 | 0.702 [0.64, 0.76] | 0.815 [0.76, 0.87] | 0.565 [0.49, 0.64] |
| sem_spec | 266 | 0.789 [0.74, 0.84] | 0.735 [0.67, 0.80] | 0.761 [0.69, 0.82] |
| baseline: n de asserts | 266 | 0.549 [0.48, 0.61] | 0.580 [0.50, 0.65] | 0.509 [0.42, 0.60] |

## T4. Diferenca pareada de AUC: completo - outro (IC 95%; * = IC exclui zero)

| Comparacao | n | efetivo vs. resto | passa vs. incorreto | efetivo vs. fraco |
|---|---|---|---|---|
| completo - sem_requisito | 266 | +0.179 [+0.11, +0.25]* | -0.014 [-0.07, +0.04] | +0.285 [+0.19, +0.38]* |
| completo - sem_spec | 266 | +0.092 [+0.05, +0.14]* | +0.066 [+0.02, +0.11]* | +0.090 [+0.04, +0.15]* |
| completo - n_asserts | 266 | +0.332 [+0.25, +0.42]* | +0.221 [+0.14, +0.31]* | +0.342 [+0.22, +0.44]* |

# RQ3 - Custo e estabilidade

## T5. Tokens por par (mediana) e custo

| Condicao / juiz | n | entrada | cache (leitura) | saida | US$ por par (mediana) | US$ total | custo de gerar o teste (mediana) |
|---|---|---|---|---|---|---|---|
| completo / claude-haiku-5-5 | 266 | 1042 | 8557 | 502 | 0.00043 (0.1x o custo de gerar) | 0.12 | 0.00431 |
| completo / gemini-3.5-flash-lite | 91 | 5487 | 0 | 85 | 0.00185 (0.7x o custo de gerar) | 0.15 | 0.00267 |
| sem_requisito / claude-haiku-5-5 | 266 | 892 | 8362 | 548 | 0.00045 (0.1x o custo de gerar) | 0.12 | 0.00431 |
| sem_spec / claude-haiku-5-5 | 266 | 1042 | 602 | 432 | 0.00033 (0.1x o custo de gerar) | 0.09 | 0.00431 |

## T6. Concordancia entre juizes (condicao completo, mesmos pares)

| Juiz secundario | n | Nota | kappa quadratico | concordancia exata | dif. <= 1 | AUC efetivo vs. resto (principal / secundario) |
|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 91 | Alinhamento | 0.893 | 64% | 96% | 0.842 / 0.787 |
| gemini-3.5-flash-lite | 91 | Consist. spec | 0.578 | 47% | 87% | 0.805 / 0.658 |
| gemini-3.5-flash-lite | 91 | Nota geral | 0.811 | 55% | 91% | 0.878 / 0.812 |

## T7. (Suplementar) AUC efetivo vs. resto da nota geral, por subgrupo (n pequeno: cautela)

| Subgrupo | n | AUC |
|---|---|---|
| variante = precise | 113 | 0.822 |
| variante = vague | 153 | 0.838 |
| servico = fastapi | 177 | 0.904 |
| servico = nestjs-realworld | 61 | 0.895 |
| servico = todoapp | 28 | 0.620 |

Figura gravada em auc_sem_sonnet45.pdf
CSV combinado (condicao completo, juiz principal) gravado em combinado_sem_sonnet45.csv
