# PrivacyDocs — scanner de dados sensíveis

Monorepo com a API e a interface web do scanner.

- **API (FastAPI):** recebe PDF, imagem ou texto e **apenas detecta** dados sensíveis.
- **Front (React):** mostra a prévia e aplica a redação **no navegador**, com `pdf.js` e `pdf-lib`.
- **Runtime determinístico:** regex + Presidio + Tesseract. Sem LLM, sem chave de API e sem acesso à internet em produção.

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
│   ├── src/App.ts                              # interface, prévia e redação locais
│   ├── Dockerfile                              # dev (Vite)
│   └── Dockerfile.prod                         # produção (Nginx não privilegiado)
├── ci/                                         # gate, testes do gate e dos workflows
├── eval/                                       # baseline e corpus do cliente (não versionado)
├── .github/workflows/
│   ├── ci.yml                                  # testes, front, baseline e Trivy
│   └── release.yml                             # imagens, SBOM, cosign e digests
└── docker-compose*.yml                         # dev, produção e deploy por digest
```

O antigo repositório `22felipefdev/redator-web` permanece apenas como histórico. A fonte canônica do front é `web/` neste repositório.

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
