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
# Imagens absurdamente grandes travariam o worker antes mesmo do OCR.
MAX_PIXELS = 25_000_000
TIMEOUT = float(os.getenv("OCR_TIMEOUT", "60"))


def _palavras_de(dados, escala):
    """Converte ``image_to_data`` em palavras já no espaço da imagem original."""
    palavras = []
    for indice, texto in enumerate(dados["text"]):
        texto = (texto or "").strip()
        if not texto or str(dados["conf"][indice]) in {"-1", "-1.0"}:
            continue
        palavras.append(
            {
                "texto": texto,
                "x": round((dados["left"][indice] - BORDA) / escala),
                "y": round((dados["top"][indice] - BORDA) / escala),
                "largura": round(dados["width"][indice] / escala),
                "altura": round(dados["height"][indice] / escala),
            }
        )
    return palavras


def _sobreposicao_area(a, b):
    largura = max(
        0, min(a["x"] + a["largura"], b["x"] + b["largura"]) - max(a["x"], b["x"])
    )
    altura = max(
        0, min(a["y"] + a["altura"], b["y"] + b["altura"]) - max(a["y"], b["y"])
    )
    return largura * altura


def _mesclar_palavras(base, extra):
    """Mantém palavras repetidas uma só vez e preserva leituras diferentes."""
    mescladas = list(base)
    for palavra in extra:
        area = max(1, palavra["largura"] * palavra["altura"])
        repetida = any(
            palavra["texto"] == existente["texto"]
            and _sobreposicao_area(palavra, existente)
            > 0.4 * min(area, existente["largura"] * existente["altura"])
            for existente in mescladas
        )
        if not repetida:
            mescladas.append(palavra)
    return mescladas


def _linhas_de(palavras):
    """Agrupa palavras por sobreposição vertical e devolve linhas ordenadas."""
    linhas = []
    for palavra in sorted(palavras, key=lambda p: (p["y"] + p["altura"] / 2, p["x"])):
        topo = palavra["y"]
        base = topo + palavra["altura"]
        melhor = None
        melhor_area = 0
        for linha in linhas:
            linha_topo = min(p["y"] for p in linha)
            linha_base = max(p["y"] + p["altura"] for p in linha)
            area = max(0, min(base, linha_base) - max(topo, linha_topo))
            if area > melhor_area:
                melhor_area = area
                melhor = linha
        if melhor is None or melhor_area < palavra["altura"] * 0.5:
            linhas.append([palavra])
        else:
            melhor.append(palavra)
    linhas.sort(key=lambda linha: min(p["y"] for p in linha))
    return linhas


def analisar_imagem(caminho):
    """Devolve ``{"texto": str, "posicoes": dict}`` da imagem original."""
    executavel = os.getenv("TESSERACT_CMD")
    if executavel:
        pytesseract.pytesseract.tesseract_cmd = executavel

    with Image.open(caminho) as imagem:
        orientada = ImageOps.exif_transpose(imagem)
        largura, altura = orientada.size
        if largura * altura > MAX_PIXELS:
            raise ValueError("imagem grande demais para processamento")
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
            timeout=TIMEOUT,
        )
        confiancas = [
            float(valor)
            for texto, valor in zip(dados["text"], dados["conf"])
            if (texto or "").strip() and str(valor) not in {"-1", "-1.0"}
        ]
        media = sum(confiancas) / len(confiancas) if confiancas else 0.0
        candidatos.append((media, _palavras_de(dados, escala)))

    # O PSM de maior confiança média é a base, mas o outro passe pode ter lido
    # um número que a base errou (ex.: 764 vs 754). Unir as palavras que não
    # colidem preserva a localização das duas ocorrências sem inventar texto.
    candidatos.sort(key=lambda item: item[0], reverse=True)
    palavras = _mesclar_palavras(candidatos[0][1], candidatos[1][1])
    linhas = _linhas_de(palavras)

    palavras_ordenadas = [
        palavra for linha in linhas for palavra in sorted(linha, key=lambda p: p["x"])
    ]
    texto = "\n".join(
        " ".join(
            palavra["texto"]
            for palavra in sorted(linha, key=lambda p: p["x"])
        )
        for linha in linhas
    )

    return {
        "texto": texto,
        "posicoes": {
            "largura": largura,
            "altura": altura,
            "palavras": palavras_ordenadas,
        },
    }
