# LLM como juiz de testes de REST API gerados por LLMs

Estudo empírico para a disciplina *IA Generativa na Engenharia de Software* (UFF, 2026).
Verifica se um LLM juiz, ao ler o requisito em linguagem natural, a especificação OpenAPI e o
código do teste, consegue antecipar a efetividade medida pelo **MS_φ** (property-based mutation
score) do [RESTestBench](https://github.com/casablancahotelsoftware/RESTestBench).

- **RQ1 (validade):** a nota do juiz separa testes efetivos, fracos e incorretos?
- **RQ2 (papel do requisito):** quanto a separação cai sem o requisito ou sem a spec? O juiz supera um baseline trivial (número de asserts)?
- **RQ3 (custo e estabilidade):** quanto custa julgar um teste comparado a gerá-lo? Dois juízes de famílias diferentes concordam?

Nenhum teste é gerado ou executado aqui, e o Docker não é necessário: o estudo reaproveita os testes
gerados e os resultados de mutação publicados no repositório do RESTestBench.

## Arquivos

| Arquivo | Função |
|---|---|
| `extrair_amostra.py` | Lê os resultados publicados do RESTestBench e monta a amostra (requisito, teste, MS_φ, categoria, n de asserts, custo de geração). |
| `amostra_restestbench.csv` | Amostra usada no estudo: 300 pares, 100 por categoria (incorreto, fraco, efetivo), seed 42. |
| `juiz_llm.py` | Juiz LLM com rubrica de 1 a 5, nas condições `completo`, `sem_requisito` e `sem_spec`. Grava incrementalmente e retoma se interrompido. |
| `repetibilidade.py` | Compara duas passagens do mesmo juiz nos mesmos pares (kappa quadrático, concordância, AUC e custo da repetição). |
| `analisar.py` | Tabelas T1–T7 em Markdown (AUC e Spearman com IC 95% por bootstrap, diferença pareada de AUC, custo, kappa entre juízes) e figura de AUC por condição. |

## 1. Preparação

Requer Python 3.11+ e git.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

git clone https://github.com/casablancahotelsoftware/RESTestBench.git
git -C RESTestBench checkout 4decc1e36ea3dd41b64ce3e3ac6a85bc72df36ae   # versão usada no estudo
```

Opcional: regenerar a amostra (sai idêntica à incluída).

```bash
python extrair_amostra.py --repo ./RESTestBench --por-categoria 100 --seed 42
```

## 2. Chaves de API

```bash
export ANTHROPIC_API_KEY=...          # PowerShell: $env:ANTHROPIC_API_KEY="..."
```

A chave do Gemini é definida no passo 5.

## 3. Piloto (obrigatório antes da rodada completa)

```bash
python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --dry-run    # só mostra o prompt
python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --limite 20
```

Leia a coluna `justificativa` de `notas_completo_claude-haiku-5-5.csv`. Se o juiz der nota alta a quase
tudo, ajuste a rubrica em `juiz_llm.py` e **apague o CSV do piloto** antes de seguir: o script retoma a
partir do que já existe no arquivo.

Rubrica usada no estudo: **v2**, refinada após o piloto (contexto do ambiente do benchmark, credenciais do
seed, conflito requisito × spec e foco da nota geral no comportamento verificado). Ver `juiz_llm.py`.

## 4. Juiz principal, três condições (RQ1 e RQ2)

```bash
python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao completo
python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao sem_requisito
python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --condicao sem_spec
```

Se algum par falhar, rode o mesmo comando de novo: só os pendentes serão avaliados.

## 5. Segundo juiz, Gemini, 100 pares (RQ3)

Use o Gemini Flash-Lite mais recente listado no Google AI Studio (no estudo: `gemini-3.5-flash-lite`).
No plano gratuito, erros 429/503 são frequentes: rode o mesmo comando de novo (só os pendentes são
avaliados) ou aumente `--pausa`.

```bash
export OPENAI_API_KEY=<chave do Gemini>   # o script usa a API do Gemini compatível com OpenAI
python juiz_llm.py --repo ./RESTestBench --provedor openai --modelo <id do gemini flash-lite> \
    --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --subamostra 100
```

## 6. Repetibilidade do juiz principal (RQ3)

O juiz roda sem temperatura fixa, então a mesma entrada pode receber notas diferentes. Para medir isso, o
Haiku julga uma segunda vez a mesma subamostra estratificada de 100 pares do Gemini (`--subamostra 100`,
seed 42), gravando em um arquivo fora do padrão `notas_*.csv` para o `analisar.py` não misturá-lo com a
primeira passagem:

```bash
python juiz_llm.py --repo ./RESTestBench --modelo claude-haiku-5-5 --subamostra 100 \
    --saida repeticao_completo_claude-haiku-5-5.csv
python repetibilidade.py > repetibilidade.md
```

O `repetibilidade.py` compara as duas passagens nos mesmos pares: kappa quadrático, concordância exata e
com diferença de até um ponto (nota geral, alinhamento e consistência com a spec), AUC de efetivo vs. resto
em cada passagem e custo da repetição. Custo no estudo: cerca de US$ 0,05.

## 7. Análise

`--preco` recebe, para cada juiz, os preços em US$ por milhão de tokens na ordem
`entrada,leitura_de_cache,escrita_de_cache,saida`, tirados das páginas oficiais de preço
(use `0,0,0,0` para o plano gratuito do Gemini).

```bash
python analisar.py --preco claude-haiku-5-5=E,CL,CE,S <id do gemini>=E,CL,0,S > resultados.md

# sensibilidade à autopreferência: sem os testes gerados pelo Claude Sonnet 4.5
python analisar.py --excluir-modelos sonnet45 --figura auc_sem_sonnet45.pdf \
    --saida combinado_sem_sonnet45.csv > resultados_sem_sonnet45.md
```

## 8. O que gera

| Arquivo | Conteúdo |
|---|---|
| `notas_<condicao>_<modelo>.csv` | Notas, justificativa, nível de esforço e tokens de cada par. |
| `resultados.md`, `resultados_sem_sonnet45.md` | Tabelas T1–T7. |
| `auc_condicoes.pdf`, `auc_sem_sonnet45.pdf` | Figura de AUC por condição com IC 95%. |
| `combinado.csv` | Amostra unida às notas do juiz principal (condição completo). |
| `repeticao_completo_claude-haiku-5-5.csv` | Segunda passagem do juiz principal em 100 pares. |
| `repetibilidade.md` | Tabela de repetibilidade (kappa, concordância, AUC e custo). |

## 9. Artigo e apresentação

| Pasta | Conteúdo |
|---|---|
| `artigo/` | Artigo em LaTeX (`artigo.tex`, `refs.bib`, classe `acmart`, 4 páginas) e o PDF compilado. |
| `apresentacao/` | Slides em LaTeX Beamer, tema Madrid (`slides.tex`), para 7 minutos, com notas do orador por slide. |

Os números do artigo e dos slides saem de `resultados.md`, `resultados_sem_sonnet45.md` e
`repetibilidade.md`. A repetibilidade do juiz (seção 6) aparece na RQ3 do artigo e no slide "Repetibilidade: o juiz concorda consigo mesmo".

```bash
cd artigo && latexmk -pdf artigo.tex                                          # gera artigo.pdf
cd apresentacao && latexmk -pdf slides.tex                                    # gera slides.pdf
cd apresentacao && pdflatex -jobname=notas "\def\SHOWNOTES{}\input{slides}"   # gera notas.pdf (notas do orador)
```

Requer TeX Live com `acmart`, `beamer`, `babel` em português e TikZ (no Ubuntu: `texlive-publishers`,
`texlive-lang-portuguese`, `texlive-latex-extra`, `texlive-fonts-extra`, `latexmk`).

## Configuração dos juízes

- Raciocínio: `--esforco medium` por padrão nos dois provedores; o nível efetivamente usado fica na coluna `esforco`.
- Temperatura: não é enviada (o Claude Haiku 5.5 pede que seja omitida), então execuções repetidas podem variar um pouco.
- O juiz nunca recebe os mutantes nem o resultado da execução dos testes.

## Atribuição e licença

`amostra_restestbench.csv` contém requisitos e testes gerados extraídos do RESTestBench, distribuído
sob a licença AGPL-3.0. Mantenha a atribuição ao RESTestBench e verifique a compatibilidade da licença
escolhida para este repositório.

## Uso de IA generativa

Os scripts deste repositório foram escritos com o auxílio do Claude (Anthropic) e revisados pelo autor.
