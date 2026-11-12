"""Extração de texto de documentos e OCR para PDFs digitalizados/imagens."""
import os
from pathlib import Path


def _preparar_imagem(imagem):
    """Corrige orientação EXIF e melhora tamanho/contraste sem dependências extras."""
    from PIL import Image, ImageEnhance, ImageOps

    imagem = ImageOps.exif_transpose(imagem)
    imagem = ImageOps.grayscale(imagem)

    # Fotos pequenas costumam perder detalhes de caracteres como 1 e 4.
    largura, altura = imagem.size
    if max(largura, altura) < 1800:
        escala = min(2.0, 1800 / max(largura, altura))
        imagem = imagem.resize(
            (round(largura * escala), round(altura * escala)), Image.Resampling.LANCZOS
        )

    imagem = ImageOps.autocontrast(imagem, cutoff=1)
    imagem = ImageEnhance.Sharpness(imagem).enhance(1.3)
    # Uma borda clara ajuda quando o documento foi fotografado ou recortado rente.
    return ImageOps.expand(imagem, border=12, fill="white")


EXTENSOES_TEXTO = {".txt", ".csv", ".json", ".log", ".py"}
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _ocr_imagem(imagem, idioma="por"):
    """Executa Tesseract. TESSERACT_CMD pode apontar para tesseract.exe no Windows."""
    try:
        import pytesseract
    except ImportError as erro:
        raise RuntimeError(
            "O OCR precisa da biblioteca pytesseract. Instale com: "
            "python -m pip install pytesseract"
        ) from erro

    executavel = os.getenv("TESSERACT_CMD")
    if executavel:
        pytesseract.pytesseract.tesseract_cmd = executavel

    try:
        # Layouts de documento e fotos com texto espalhado podem exigir segmentações
        # diferentes. Tentamos ambas e preferimos a que tem maior confiança média.
        # A confiança é apenas uma heurística; números críticos ainda devem ser revistos.
        candidatos = []
        for psm in (3, 11):
            dados = pytesseract.image_to_data(
                imagem, lang=idioma, config=f"--oem 3 --psm {psm}",
                output_type=pytesseract.Output.DICT,
            )
            texto_com_formatacao = pytesseract.image_to_string(
                imagem, lang=idioma, config=f"--oem 3 --psm {psm}"
            ).strip()
            palavras = [
                (texto or "").strip()
                for texto in dados["text"]
                if (texto or "").strip()
            ]
            confiancas = [
                float(valor) for texto, valor in zip(dados["text"], dados["conf"])
                if (texto or "").strip() and str(valor) not in {"-1", "-1.0"}
            ]
            if palavras:
                score = sum(confiancas) / len(confiancas) if confiancas else 0
                candidatos.append((score, texto_com_formatacao))
        if candidatos:
            return max(candidatos, key=lambda item: item[0])[1]
        return ""
    except pytesseract.TesseractNotFoundError as erro:
        raise RuntimeError(
            "Não encontrei o Tesseract OCR. Instale o Tesseract para Windows e "
            "o idioma português (por). Se necessário, defina a variável "
            "TESSERACT_CMD apontando para tesseract.exe."
        ) from erro
    except pytesseract.TesseractError as erro:
        raise RuntimeError(
            f"Falha no OCR. Confirme se o idioma '{idioma}' está instalado no Tesseract."
        ) from erro


def extrair_texto(caminho, idioma="por"):
    """Extrai texto nativo e usa OCR como fallback em PDFs sem camada textual."""
    arquivo = Path(caminho)
    extensao = arquivo.suffix.lower()

    if extensao in EXTENSOES_TEXTO:
        return arquivo.read_text(encoding="utf-8", errors="ignore")

    if extensao == ".pdf":
        try:
            import pdfplumber
        except ImportError as erro:
            raise RuntimeError(
                "Para ler PDFs, instale pdfplumber: python -m pip install pdfplumber"
            ) from erro

        textos = []
        with pdfplumber.open(arquivo) as pdf:
            for numero, pagina in enumerate(pdf.pages, start=1):
                texto = (pagina.extract_text() or "").strip()
                # Algumas páginas podem ter texto e outras ser digitalizadas.
                if not texto:
                    imagem = _preparar_imagem(pagina.to_image(resolution=300).original)
                    texto = _ocr_imagem(imagem, idioma).strip()
                if texto:
                    textos.append(f"[Página {numero}]\n{texto}")
        return "\n\n".join(textos)

    if extensao in EXTENSOES_IMAGEM:
        try:
            from PIL import Image
        except ImportError as erro:
            raise RuntimeError(
                "Para OCR de imagens, instale Pillow: python -m pip install Pillow"
            ) from erro

        with Image.open(arquivo) as imagem:
            imagem = _preparar_imagem(imagem)
            return _ocr_imagem(imagem, idioma).strip()

    raise ValueError(f"Formato não suportado para extração de texto: {extensao}")
