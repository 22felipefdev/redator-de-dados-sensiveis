"""API HTTP do scanner. O OCR/Presidio continuam exatamente os mesmos."""
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from detector import identificar_dados_sensiveis
from ocr import EXTENSOES_IMAGEM, EXTENSOES_TEXTO, extrair_texto
from ocr_posicoes import obter_posicoes
from presidio_detector import analisar_texto
from regex_parser import extrair_evidencias

app = FastAPI(title="PrivacyDocs Scanner", version="1.0.0")

# Em produção, restrinja à origem real do front-end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EXTENSOES_ACEITAS = EXTENSOES_TEXTO | EXTENSOES_IMAGEM | {".pdf"}


@app.get("/api/saude")
def saude():
    return {"status": "ok"}


@app.post("/api/analisar")
def analisar(arquivo: UploadFile = File(...)):
    """Recebe o arquivo e devolve os itens confirmados por regex + Presidio."""
    nome = arquivo.filename or ""
    extensao = Path(nome).suffix.lower()

    if extensao not in EXTENSOES_ACEITAS:
        raise HTTPException(
            400,
            f"Formato não suportado: {extensao or 'sem extensão'}. "
            "Use PDF, imagem ou arquivo de texto.",
        )

    conteudo = arquivo.file.read()
    if not conteudo:
        raise HTTPException(400, "Arquivo vazio.")

    # Rotas síncronas rodam em thread pool: o OCR não bloqueia outras requests.
    try:
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / f"entrada{extensao}"
            caminho.write_bytes(conteudo)
            texto = extrair_texto(caminho)
            posicoes = obter_posicoes(caminho) if extensao in EXTENSOES_IMAGEM else None
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from erro
    except Exception as erro:
        raise HTTPException(500, f"Falha ao extrair texto: {erro}") from erro

    evidencias = extrair_evidencias(texto)
    resultados = analisar_texto(texto)
    relatorio = identificar_dados_sensiveis(texto, evidencias, resultados)

    return {
        "arquivo": nome,
        "texto": texto,
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
