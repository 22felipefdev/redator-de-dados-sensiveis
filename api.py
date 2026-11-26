"""API HTTP do scanner. O OCR/Presidio continuam exatamente os mesmos."""
import hashlib
import logging
import os
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from detector import identificar_dados_sensiveis
from ocr import EXTENSOES_IMAGEM, EXTENSOES_TEXTO, extrair_texto
from ocr_posicoes import analisar_imagem
from presidio_detector import analisar_texto
from regex_parser import extrair_evidencias

logger = logging.getLogger("privacydocs")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(_handler)
logger.propagate = False

# Em produção não expomos documentação/OpenAPI: superfície de ataque menor.
producao = os.getenv("AMBIENTE", "").strip().lower() == "producao"
app = FastAPI(
    title="PrivacyDocs Scanner",
    version="1.0.0",
    docs_url=None if producao else "/docs",
    redoc_url=None if producao else "/redoc",
    openapi_url=None if producao else "/openapi.json",
)

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
CACHE_MAXIMO = 64  # entradas em memória; nada de PII gravado em disco

# OCR/PDF são CPU-bound: sem limite, várias requisições competem e ficam todas lentas.
OCR_CONCORRENCIA = max(1, int(os.getenv("OCR_CONCORRENCIA", "2")))
FILA_ESPERA = max(0.0, float(os.getenv("FILA_ESPERA", "5")))
_limite_ocr = threading.BoundedSemaphore(OCR_CONCORRENCIA)


def _versao_ocr():
    """Invalida o cache quando o pré-processamento ou o OCR mudar."""
    digest = hashlib.sha1()
    for nome in ("ocr.py", "ocr_posicoes.py"):
        caminho = Path(__file__).with_name(nome)
        if caminho.exists():
            digest.update(caminho.read_bytes())
    return digest.hexdigest()[:8]


VERSAO_CACHE = _versao_ocr()
_cache: OrderedDict[str, dict] = OrderedDict()

MENSAGEM_INVALIDO = "Arquivo inválido ou formato não suportado."


def contar_evidencias(evidencias):
    """Conta grupos com achado e total de candidatos antes da interseção.

    ``len(evidencias)`` devolve sempre 7: é o número de chaves do dicionário,
    não o que o regex encontrou.
    """
    return (
        sum(1 for valores in evidencias.values() if valores),
        sum(len(valores) for valores in evidencias.values()),
    )


# Contrato explícito: nenhum campo novo criado por acidente sai da API.
class PalavraResponse(BaseModel):
    texto: str
    x: int
    y: int
    largura: int
    altura: int


class PosicoesResponse(BaseModel):
    largura: int
    altura: int
    palavras: list[PalavraResponse]


class ItemResponse(BaseModel):
    dado: str
    tipo: str
    risco: str
    revisar: bool = False
    original: str | None = None


class AnaliseResponse(BaseModel):
    arquivo: str
    posicoes: PosicoesResponse | None = None
    itens: list[ItemResponse]


def _chave_cache(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest() + VERSAO_CACHE


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


@app.post("/api/analisar", response_model=AnaliseResponse)
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

    # Rotas síncronas rodam em thread pool: limitamos quantas fazem OCR/PDF ao mesmo tempo.
    inicio = time.perf_counter()
    chave = _chave_cache(conteudo) if extensao in EXTENSOES_IMAGEM else None
    leitura = _cache.get(chave) if chave else None

    if leitura is None:
        if not _limite_ocr.acquire(timeout=FILA_ESPERA):
            raise HTTPException(
                503,
                "Servidor ocupado. Tente novamente em instantes.",
                headers={"Retry-After": str(max(1, int(FILA_ESPERA)))},
            )
        try:
            # Outra request pode ter preenchido o cache enquanto esperávamos na fila.
            leitura = _cache.get(chave) if chave else None
            if leitura is None:
                with tempfile.TemporaryDirectory() as temporario:
                    caminho = Path(temporario) / f"entrada{extensao}"
                    caminho.write_bytes(conteudo)
                    if extensao in EXTENSOES_IMAGEM:
                        leitura = analisar_imagem(caminho)
                        _cache[chave] = leitura
                        _cache.move_to_end(chave)
                        while len(_cache) > CACHE_MAXIMO:
                            _cache.popitem(last=False)
                    else:
                        leitura = {
                            "texto": extrair_texto(caminho),
                            "posicoes": None,
                        }
        except Exception:
            # Detalhes ficam no servidor; o cliente não recebe caminhos nem versões.
            logger.exception("Falha ao extrair texto de extensão %s", extensao)
            raise HTTPException(500, "Não foi possível ler o arquivo.") from None
        finally:
            _limite_ocr.release()

    texto = leitura["texto"]
    posicoes = leitura["posicoes"]
    logger.info(
        "extracao concluida em %.0f ms (%d palavras)",
        (time.perf_counter() - inicio) * 1000,
        len(posicoes["palavras"]) if posicoes else 0,
    )

    inicio_deteccao = time.perf_counter()
    evidencias = extrair_evidencias(texto)
    resultados = analisar_texto(texto)
    relatorio = identificar_dados_sensiveis(texto, evidencias, resultados)
    # Quantos tipos o regex encontrou e quantos candidatos entraram no pipeline.
    grupos_regex, candidatos_regex = contar_evidencias(evidencias)
    logger.info(
        "deteccao concluida em %.0f ms: "
        "grupos_regex=%d candidatos_regex=%d presidio=%d itens=%d",
        (time.perf_counter() - inicio_deteccao) * 1000,
        grupos_regex,
        candidatos_regex,
        len(resultados),
        len(relatorio.itens),
    )

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
