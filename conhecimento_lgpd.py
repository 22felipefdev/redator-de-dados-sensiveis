"""Referências da LGPD anexadas às sugestões da IA.

A referência é determinística: vem do texto da lei em ``knowledge/lgpd.json``.
O modelo nunca cria artigo, texto de lei ou explicação jurídica.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

CAMINHO = Path(__file__).with_name("knowledge") / "lgpd.json"


@lru_cache(maxsize=1)
def carregar() -> dict:
    """Lê a base uma vez por processo; sem arquivo, devolve base vazia."""
    if not CAMINHO.is_file():
        logger.warning("Base de LGPD não encontrada em %s", CAMINHO)
        return {"url": "", "artigos": [], "categorias": {}, "notas": {}}
    return json.loads(CAMINHO.read_text(encoding="utf-8"))


def referencias(categoria: str) -> list[dict]:
    """Devolve os recortes oficiais ligados a uma categoria da IA."""
    dados = carregar()
    indice = {artigo["id"]: artigo for artigo in dados.get("artigos", [])}

    resultado = []
    for identificador in dados.get("categorias", {}).get(categoria, []):
        artigo = indice.get(identificador)
        if not artigo:
            continue
        resultado.append(
            {
                "id": identificador,
                "titulo": artigo["titulo"],
                "texto": artigo["texto"],
                "tipo": artigo["tipo"],
                "url": dados.get("url", ""),
            }
        )
    return resultado


def nota(categoria: str) -> str:
    """Nota de ressalva, por exemplo sobre interpretação doutrinária."""
    return carregar().get("notas", {}).get(categoria, "")
