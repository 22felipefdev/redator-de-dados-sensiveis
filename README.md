# redator-de-dados-sensiveis

API FastAPI que detecta dados sensíveis em PDF, imagem e texto. A redação acontece no navegador; a API devolve apenas metadados e posições.

## Verificação

```bash
python -m pip install --require-hashes -r requirements.lock.txt
python ci/verificar.py
```

O gate checa sintaxe, testes do gate e do lock, testes da API, recall (mínimo 99%), falsos positivos (máximo 2), build/lint do front e vulnerabilidades. Use `--container <nome>` quando o Python local não tiver FastAPI e `--exigir-baseline` quando `eval/corpus` estiver disponível.

## Supply chain

- `requirements.lock.txt`: todas as dependências, incluindo o modelo spaCy, com hash SHA-256. O Dockerfile instala com `--require-hashes`.
- Imagens-base fixadas por digest nos Dockerfiles (API, Node e Nginx).
- `.github/workflows/ci.yml`: Ações fixadas por SHA, `pip-audit` no lock e Trivy na imagem.
- `.github/workflows/release.yml`: publica imagens, gera SBOM SPDX com Syft, assina/atesta com cosign keyless e verifica antes de concluir.
- O deploy usa `tag@sha256:...` via `docker-compose.release.yml` no projeto do front; o workflow disponibiliza os digests como artefatos `evidencias-api` e `evidencias-web`.

O job do front no release só é executado quando a variável `WEB_REPO` (ou o input `web_repo`) aponta para o repositório do React, que hoje é uma pasta local sem git.
