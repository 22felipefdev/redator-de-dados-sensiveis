"""Leitura única do OCR para imagens: texto e posições das palavras.

Antes o texto vinha de image_to_string e as posições de outra rodada de
image_to_data (até 6 chamadas ao Tesseract por imagem). Aqui as duas saídas
vêm dos mesmos dados, escolhendo o PSM por confiança média como em ocr.py.
"""
import os

import pytesseract
from PIL import Image, ImageOps

from ocr import _preparar_imagem

BORDA = 12
LADO_MINIMO = 1800
IDIOMA = "por"


def analisar_imagem(caminho):
    """Devolve ``{"texto": str, "posicoes": dict}`` da imagem original."""
    executavel = os.getenv("TESSERACT_CMD")
    if executavel:
        pytesseract.pytesseract.tesseract_cmd = executavel

    with Image.open(caminho) as imagem:
        orientada = ImageOps.exif_transpose(imagem)
        largura, altura = orientada.size
        preparada = _preparar_imagem(imagem)

    # A mesma escala aplicada em _preparar_imagem; usada para voltar às
    # coordenadas da imagem que o navegador mostra.
    escala = 1.0
    if max(largura, altura) < LADO_MINIMO:
        escala = min(2.0, LADO_MINIMO / max(largura, altura))

    candidatos = []
    for psm in (3, 11):
        dados = pytesseract.image_to_data(
            preparada,
            lang=IDIOMA,
            config=f"--oem 3 --psm {psm}",
            output_type=pytesseract.Output.DICT,
        )
        confiancas = [
            float(valor)
            for texto, valor in zip(dados["text"], dados["conf"])
            if (texto or "").strip() and str(valor) not in {"-1", "-1.0"}
        ]
        media = sum(confiancas) / len(confiancas) if confiancas else 0.0
        candidatos.append((media, dados))

    dados = max(candidatos, key=lambda item: item[0])[1]

    palavras = []
    linhas = []
    chave_linha = None
    linha_atual = []

    for indice, texto in enumerate(dados["text"]):
        texto = (texto or "").strip()
        if not texto or str(dados["conf"][indice]) in {"-1", "-1.0"}:
            continue

        chave = (
            dados["block_num"][indice],
            dados["par_num"][indice],
            dados["line_num"][indice],
        )
        if chave != chave_linha:
            if linha_atual:
                linhas.append(" ".join(linha_atual))
            linha_atual = []
            chave_linha = chave
        linha_atual.append(texto)

        palavras.append(
            {
                "texto": texto,
                "x": round((dados["left"][indice] - BORDA) / escala),
                "y": round((dados["top"][indice] - BORDA) / escala),
                "largura": round(dados["width"][indice] / escala),
                "altura": round(dados["height"][indice] / escala),
            }
        )

    if linha_atual:
        linhas.append(" ".join(linha_atual))

    return {
        "texto": "\n".join(linhas),
        "posicoes": {
            "largura": largura,
            "altura": altura,
            "palavras": palavras,
        },
    }
