# Front React

Interface web do scanner, escrita em TypeScript **sem JSX** (`React.createElement` em `src/App.ts`). A API apenas detecta; a prévia e a redação acontecem no navegador com `pdf.js` e `pdf-lib`.

## Executar

Na raiz do monorepo:

```bash
docker compose up -d --build   # API em :8000 e front em :5173
```

Sem Docker, a partir da raiz do repositório:

```bash
npm ci --prefix web
API_URL=http://localhost:8000 npm run dev --prefix web
```

`API_URL` é necessário fora do Compose: o proxy padrão do Vite aponta para `http://api:8000`, nome de serviço que só existe na rede do Docker.

## Verificar

```bash
npm run build --prefix web
npm run lint --prefix web
```

O gate `python ci/verificar.py` já executa ambos.

## Imagem

`Dockerfile.prod` gera o build estático em Nginx não privilegiado (porta 8080). O workflow de Release publica `ghcr.io/<owner>/<repo>/web:<tag>` a partir deste diretório.
