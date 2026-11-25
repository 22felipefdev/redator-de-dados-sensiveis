"""API HTTP do scanner. O OCR/Presidio continuam exatamente os mesmos."""
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from detector import identificar_dados_sensiveis
from ocr import EXTENSOES_IMAGEM, EXTENSOES_TEXTO, extrair_texto
from ocr_posicoes import analisar_imagem
from presidio_detector import analisar_texto
from regex_parser import extrair_evidencias

logger = logging.getLogger("privacydocs")

app = FastAPI(title="PrivacyDocs Scanner", version="1.0.0")

# Origens configuráveis: em produção, defina CORS_ORIGINS com o domínio real.
origens = [
    origem.strip()
    for origem in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origem.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

EXTENSOES_ACEITAS = EXTENSOES_TEXTO | EXTENSOES_IMAGEM | {".pdf"}
TAMANHO_MAXIMO = 20 * 1024 * 1024  # 20 MiB

MENSAGEM_INVALIDO = "Arquivo inválido ou formato não suportado."


def assinatura_valida(conteudo: bytes, extensao: str) -> bool:
    """Confere o tipo real pelo cabeçalho, não apenas pela extensão."""
    if extensao in EXTENSOES_TEXTO:
        try:
            conteudo.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    if extensao == ".pdf":
        return conteudo.startswith(b"%PDF-")
    if extensao == ".png":
        return conteudo.startswith(b"\x89PNG\r\n\x1a\n")
    if extensao in {".jpg", ".jpeg"}:
        return conteudo.startswith(b"\xff\xd8\xff")
    if extensao == ".webp":
        return conteudo.startswith(b"RIFF") and conteudo[8:12] == b"WEBP"
    if extensao == ".bmp":
        return conteudo.startswith(b"BM")
    if extensao in {".tif", ".tiff"}:
        return conteudo.startswith((b"II*\x00", b"MM\x00*"))
    return False


@app.get("/api/saude")
def saude():
    return {"status": "ok"}


@app.post("/api/analisar")
def analisar(arquivo: UploadFile = File(...)):
    """Recebe o arquivo e devolve os itens confirmados por regex + Presidio."""
    # nome é só o basename: nunca usamos o caminho enviado pelo cliente.
    nome = Path(arquivo.filename or "").name
    extensao = Path(nome).suffix.lower()

    if extensao not in EXTENSOES_ACEITAS:
        raise HTTPException(400, MENSAGEM_INVALIDO)

    tamanho = arquivo.headers.get("content-length")
    if tamanho and tamanho.isdigit() and int(tamanho) > TAMANHO_MAXIMO:
        raise HTTPException(413, "Arquivo maior que o limite de 20 MB.")

    # Lê no máximo o limite + 1 byte: nunca carrega um arquivo gigante na memória.
    conteudo = arquivo.file.read(TAMANHO_MAXIMO + 1)
    if len(conteudo) > TAMANHO_MAXIMO:
        raise HTTPException(413, "Arquivo maior que o limite de 20 MB.")
    if not conteudo or not assinatura_valida(conteudo, extensao):
        raise HTTPException(400, MENSAGEM_INVALIDO)

    # Rotas síncronas rodam em thread pool: o OCR não bloqueia outras requests.
    try:
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / f"entrada{extensao}"
            caminho.write_bytes(conteudo)

            if extensao in EXTENSOES_IMAGEM:
                leitura = analisar_imagem(caminho)
                texto = leitura["texto"]
                posicoes = leitura["posicoes"]
            else:
                texto = extrair_texto(caminho)
                posicoes = None
    except Exception:
        # Detalhes ficam no servidor; o cliente não recebe caminhos nem versões.
        logger.exception("Falha ao extrair texto de %s", nome)
        raise HTTPException(500, "Não foi possível ler o arquivo.") from None

    evidencias = extrair_evidencias(texto)
    resultados = analisar_texto(texto)
    relatorio = identificar_dados_sensiveis(texto, evidencias, resultados)

    return {
        "arquivo": nome,
        "posicoes": posicoes,
        "itens": [
            {
                "dado": item.dado,
                "tipo": item.tipo,
                "risco": item.risco,
                "revisar": item.revisar,
                "original": item.original,
            }
            for item in relatorio.itens
        ],
    }
