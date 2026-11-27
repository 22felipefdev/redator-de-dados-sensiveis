# PrivacyDocs — scanner de dados sensíveis

Monorepo com a API e a interface web do scanner.

- **API (FastAPI):** recebe PDF, imagem ou texto e **apenas detecta** dados sensíveis.
- **Front (React):** mostra a prévia, separa o que regex/Presidio decidiu das sugestões da IA (sempre desmarcadas) e aplica a redação **no navegador**, com `pdf.js` e `pdf-lib`.
- **Runtime determinístico por padrão:** regex + Presidio + Tesseract. A IA de contexto é opt-in (`IA_CONTEXTO=1`), nunca cria ou corrige dados, e as referências LGPD são anexadas pela API.

A API não devolve o documento: responde com os trechos detectados, classificação, risco, sinalização de revisão e — para imagens/PDFs digitalizados — as posições das palavras para o navegador pintar a redação.

## Estrutura

```text
.
├── api.py, detector.py, ocr.py, ocr_posicoes.py,
│   presidio_detector.py, regex_parser.py       # API e pipeline de detecção
├── test_api.py                                 # testes da API e do detector
├── Dockerfile                                  # imagem da API (Tesseract + pt)
├── requirements.lock.txt                       # dependências com hash SHA-256
├── web/                                        # front React/TypeScript (sem JSX)
│   ├── src/App.ts                              # fluxo envio → revisão → download
│   ├── src/components/redactor/                # cabeçalho, upload, prévia, achados, resultado
│   ├── src/lib/redactor/                       # contrato, API, detecção e pdf.js/pdf-lib
│   ├── Dockerfile                              # dev (Vite)
│   └── Dockerfile.prod                         # produção (Nginx não privilegiado)
├── ci/                                         # gate, testes do gate e dos workflows
├── eval/                                       # baseline e corpus do cliente (não versionado)
├── .github/workflows/
│   ├── ci.yml                                  # testes, front, baseline e Trivy
│   └── release.yml                             # imagens, SBOM, cosign e digests
└── docker-compose*.yml                         # dev, produção e deploy por digest
```

O antigo repositório `22felipefdev/redator-web` permanece apenas como histórico. A fonte canônica do front é `web/` neste repositório. O visual foi portado do protótipo `redesign-de-app-redator`, mas a implementação usa Vite/React com `React.createElement` em arquivos `.ts` (sem JSX), Tailwind 4 via PostCSS e fontes IBM Plex. A prévia e as tarjas são aplicadas no navegador (`pdf.js`/`pdf-lib`); a API apenas classifica. Imagens usam OCR com coordenadas quando `posicoes` está presente, e arquivos de texto voltam intactos — só são sinalizados. Nenhum nome de fornecedor ou modelo aparece na interface.

## Executando

### Docker (recomendado)

```bash
docker compose up -d --build
```

| Serviço | Endereço | Observação |
| --- | --- | --- |
| API | http://localhost:8000 | `/api/saude` e `/api/analisar` |
| Front | http://localhost:5173 | proxy `/api` → `http://api:8000` |

Produção, sem recarga de código e com rootfs somente leitura:

```bash
API_PORT=8001 WEB_PORT=5174 docker compose -f docker-compose.prod.yml up -d --build
```

Deploy por digest (os valores vêm dos artefatos `evidencias-api` e `evidencias-web` do Release):

```bash
IMAGEM_API=ghcr.io/22felipefdev/redator-de-dados-sensiveis/api:v1.0.0@sha256:... \
IMAGEM_WEB=ghcr.io/22felipefdev/redator-de-dados-sensiveis/web:v1.0.0@sha256:... \
  docker compose -f docker-compose.prod.yml -f docker-compose.release.yml up -d
```

### Sem Docker

API (Python 3.13):

```bash
python -m venv .venv
.\.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

Front (Node 22+):

```bash
npm ci --prefix web
API_URL=http://localhost:8000 npm run dev --prefix web
```

`API_URL` é necessário fora do Compose: por padrão o Vite usa `http://api:8000`, nome que só existe na rede do Docker. Em produção real, defina `CORS_ORIGINS` com o domínio HTTPS do front.

Para OCR local no Windows, instale o Tesseract com o idioma português (`por`) e, se o executável não estiver no `PATH`, defina `TESSERACT_CMD`. No Linux, `apt-get install tesseract-ocr tesseract-ocr-por` é suficiente.

### Sugestões contextuais da IA (laboratório)

Desligadas por padrão para manter o gate determinístico. Para testar no front:

1. Coloque a chave do provedor no `.env` da raiz (ignorado pelo Git): `IA_API_KEY=...` ou, se continuar no OpenRouter, `OPENROUTER_API_KEY=...`.
2. Acrescente `IA_CONTEXTO=1` nesse mesmo `.env`.
3. Rode `docker compose up --build` e abra `http://localhost:5173`.

Sem Docker, defina as duas variáveis no terminal antes do `uvicorn`. As sugestões aparecem com o selo **IA** e **checklist desmarcado**; CPF/RG/cartão/e-mail/ofício continuam sendo decididos por regex/Presidio. O contrato expõe `origem: "contexto"` — nunca o fornecedor ou o modelo.

A chamada ao modelo tem limite duro de **60 s** (`IA_TEMPO_TOTAL`): se o provedor demorar mais, a API devolve `itens` sem sugestões contextuais em vez de prender a resposta. A resposta que chegar depois fica em cache por conteúdo: reenviar o mesmo documento não gasta cota nem repete a espera. O front mostra um aviso próprio após 12 s e aborta em 90 s.

O adaptador aceita qualquer endpoint compatível com OpenAI. O padrão continua sendo o OpenRouter; se a cota diária acabar (HTTP 429), o log avisa e, sem créditos, ela reinicia às **21:00 (Brasília)**. Criar outra chave ou conta não aumenta o limite: o OpenRouter governa a cota globalmente.

Opções para testar sem depender dessa cota:

| Serviço | `IA_BASE_URL` | `IA_MODELO` sugerido | Condição real |
| --- | --- | --- | --- |
| Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.5-flash-lite` | Free tier de verdade; limites por projeto e RPD resetado à meia-noite (Pacific). **No free tier o Google usa os prompts para melhorar produtos** — use só atestado sintético. |
| Cerebras | `https://api.cerebras.ai/v1` | `qwen-3.8-27b` | US$ 5 de crédito de teste por 30 dias com método de pagamento verificado; não é gratuito permanente. ~300 RPM no trial. |
| Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-20b` | Plano gratuito com limites menores; confira em `console.groq.com/settings/limits`. A tabela pública de limites é do plano Developer. |
| OpenRouter | padrão | `nvidia/nemotron-3.5-super-vl:free` | 50 requisições/dia sem créditos; lento em atestados longos. |

GitHub Models foi descontinuado em 30/07/2026 — não usar.

Para trocar de provedor, edite o `.env` (o Compose já repassa as variáveis):

```dotenv
IA_CONTEXTO=1
IA_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
IA_MODELO=gemini-3.5-flash-lite
IA_API_KEY=...
```

`IA_API_KEY` é a chave do provedor escolhido; `OPENROUTER_API_KEY` continua valendo como fallback. A chave do Gemini vem de `aistudio.google.com/apikey` e começa com `AIza` (ou `AQ` em chaves recentes) — a chave do OpenRouter **não** serve para ele (o script avisa se os prefixos não combinarem). Com o Gemini, o adaptador usa function calling em vez de `json_object`. Nenhum nome de fornecedor/modelo aparece na resposta da API.

Para checar modelo sem queimar cota:

```bash
python eval/verificar_modelo.py                                      # 0 requisições de inferência
python eval/verificar_modelo.py --base-url https://api.cerebras.ai/v1 --modelo qwen-3.8-27b
python eval/verificar_modelo.py --base-url https://api.groq.com/openai/v1 --modelo openai/gpt-oss-20b --ping   # 1 requisição mínima
python eval/verificar_modelo.py --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --modelo gemini-3.5-flash-lite --real   # 1 atestado sintético
```

No OpenRouter o script mostra `is_free_tier`, `creditos restantes` e `free_model_daily_requests`; nos demais, consulta `/models`, se disponível. **Nunca rode `--real` com documento real**: o modo usa o atestado sintético embutido no script.

### Corpus e referência de LGPD

Dois corpus separados, com papéis diferentes:

- `knowledge/lgpd.json` — recortes oficiais da Lei nº 13.709/2018 e mapeamento `categoria → artigo`. É versionado, não contém PII e alimenta o campo `referencias_lgpd` da resposta. A referência é anexada por `conhecimento_lgpd.py` **depois** da IA, de forma determinística: o modelo nunca cria artigo nem explicação jurídica. Trechos que não estão literalmente na lei (ex.: planejamento familiar) vêm marcados como `"tipo": "interpretacao"`.
- `eval/corpus/contextos.jsonl` — documentos **falsos** com o esperado por caso. Não é versionado. Os índices são calculados, nunca digitados à mão.

```bash
python eval/avaliar_contexto.py --modo mock   # sem rede: testa validação e métricas
python eval/avaliar_contexto.py --modo live   # chama o modelo; números variam
python eval/avaliar_contexto.py --modo live --exigir   # falha se recall < 100 ou FP > 0
```

O modo `live` **não** entra no gate do CI, que precisa continuar determinístico.

## Contrato da API

| Rota | Uso |
| --- | --- |
| `GET /api/saude` | verificação de vida (`{"status":"ok"}`) |
| `POST /api/analisar` | upload multipart em `arquivo`; resposta `AnaliseResponse` |

```json
{
  "arquivo": "contrato.pdf",
  "posicoes": {
    "largura": 1240,
    "altura": 1754,
    "palavras": [{"texto": "CPF:", "x": 72, "y": 180, "largura": 30, "altura": 12}]
  },
  "itens": [
    {"dado": "123.456.789-09", "tipo": "CPF", "risco": "high", "revisar": false, "original": null}
  ]
}
```

`posicoes` existe quando há OCR com coordenadas. Texto puro apenas sinaliza os itens; a redação do PDF original é feita no navegador. O contrato é fixado por `response_model` (Pydantic usado apenas nos modelos de resposta do FastAPI).

## Verificação

```bash
python ci/verificar.py
python ci/verificar.py --exigir-baseline   # quando eval/corpus estiver disponível
```

O gate verifica: sintaxe, testes do gate/lock/workflows, testes da API, `npm run build` e `npm run lint` em `web/`, recall **≥ 99%**, no máximo **2** falsos positivos e auditoria de dependências/imagem. Use `--container redator-api-1` quando o Python local não tiver FastAPI. O corpus do cliente não é versionado; sem ele o baseline é avisado e ignorado, a menos que `--exigir-baseline` seja usado.

## Segurança e supply chain

- `requirements.lock.txt` registra todas as dependências, incluindo o modelo spaCy, com hash SHA-256. O Dockerfile instala com `--require-hashes`.
- Imagens-base (Python, Node e Nginx) e Ações do GitHub fixadas por digest/SHA.
- `.github/workflows/ci.yml`: `pip-audit` no lock e Trivy na imagem. O Trivy ignora somente `pip/_vendor/vendor.txt` e `pip/_vendor/bom.cdx.json`, manifestos internos do pip que fixam versões vendidas diferentes das instaladas na aplicação.
- `.github/workflows/release.yml`: publica `ghcr.io/<owner>/<repo>/api:*` e `/web:*`, gera SBOM SPDX com Syft, assina e atesta com cosign keyless, verifica por digest e publica os digests como artefatos.
- Nenhuma PII é gravada em disco pela API; o cache de OCR é em memória.

## Release

Ao publicar uma tag `v*`, o workflow gera as duas imagens a partir deste repositório. A release `v1.0.0` está publicada com assinatura, atestação SPDX e digests; a tag aponta para o commit do monorepo unificado.
