import os
import zipfile


TIPOS_EXTENSAO = {
    ".pdf": ("PDF", "Documento"),
    ".txt": ("Arquivo de texto", "Documento"),
    ".doc": ("Documento Word", "Documento"),
    ".docx": ("Documento Word", "Documento"),
    ".xls": ("Planilha Excel", "Planilha"),
    ".xlsx": ("Planilha Excel", "Planilha"),
    ".ppt": ("Apresentação PowerPoint", "Apresentação"),
    ".pptx": ("Apresentação PowerPoint", "Apresentação"),
    ".csv": ("Arquivo CSV", "Dados"),
    ".json": ("Arquivo JSON", "Dados"),
    ".xml": ("Arquivo XML", "Dados"),
    ".html": ("Página HTML", "Web"),
    ".htm": ("Página HTML", "Web"),
    ".css": ("Folha de estilos CSS", "Web"),
    ".js": ("Código JavaScript", "Código"),
    ".py": ("Código Python", "Código"),
    ".java": ("Código Java", "Código"),
    ".c": ("Código C", "Código"),
    ".cpp": ("Código C++", "Código"),
    ".cs": ("Código C#", "Código"),
    ".jpg": ("Imagem JPEG", "Imagem"),
    ".jpeg": ("Imagem JPEG", "Imagem"),
    ".png": ("Imagem PNG", "Imagem"),
    ".gif": ("Imagem GIF", "Imagem"),
    ".bmp": ("Imagem BMP", "Imagem"),
    ".webp": ("Imagem WebP", "Imagem"),
    ".mp3": ("Áudio MP3", "Áudio"),
    ".wav": ("Áudio WAV", "Áudio"),
    ".ogg": ("Áudio OGG", "Áudio"),
    ".mp4": ("Vídeo MP4", "Vídeo"),
    ".avi": ("Vídeo AVI", "Vídeo"),
    ".mkv": ("Vídeo MKV", "Vídeo"),
    ".zip": ("Arquivo ZIP", "Compactado"),
    ".rar": ("Arquivo RAR", "Compactado"),
    ".7z": ("Arquivo 7-Zip", "Compactado"),
}


ASSINATURAS = {
    b"%PDF-": ("PDF", "Documento"),
    b"\x89PNG\r\n\x1a\n": ("PNG", "Imagem"),
    b"\xff\xd8\xff": ("JPEG", "Imagem"),
    b"GIF87a": ("GIF", "Imagem"),
    b"GIF89a": ("GIF", "Imagem"),
    b"RIFF": ("RIFF", "Arquivo multimídia"),
    b"PK\x03\x04": ("ZIP ou formato baseado em ZIP", "Compactado/Documento"),
    b"ID3": ("MP3", "Áudio"),
}


def tamanho_formatado(tamanho):
    unidades = ["B", "KB", "MB", "GB"]

    valor = float(tamanho)

    for unidade in unidades:
        if valor < 1024 or unidade == unidades[-1]:
            return f"{valor:.2f} {unidade}"
        valor /= 1024


def identificar_por_conteudo(caminho):
    try:
        with open(caminho, "rb") as arquivo:
            inicio = arquivo.read(16)

        for assinatura, resultado in ASSINATURAS.items():
            if inicio.startswith(assinatura):
                return resultado

    except (OSError, PermissionError):
        pass

    return None


def identificar_arquivo(caminho):
    try:
        nome = os.path.basename(caminho)
        extensao = os.path.splitext(nome)[1].lower()
        tamanho = os.path.getsize(caminho)

        tipo_conteudo = identificar_por_conteudo(caminho)

        if tipo_conteudo:
            tipo, categoria = tipo_conteudo
        elif extensao in TIPOS_EXTENSAO:
            tipo, categoria = TIPOS_EXTENSAO[extensao]
        else:
            tipo = "Tipo desconhecido"
            categoria = "Desconhecida"

        resultado = (
            "INFORMAÇÕES DO ARQUIVO\n"
            "----------------------------------------\n"
            f"Nome: {nome}\n"
            f"Extensão: {extensao if extensao else 'Sem extensão'}\n"
            f"Tamanho: {tamanho_formatado(tamanho)}\n"
            f"Tipo identificado: {tipo}\n"
            f"Categoria: {categoria}\n"
            "----------------------------------------\n"
        )

        if tipo_conteudo:
            resultado += "Identificação: baseada no conteúdo do arquivo."
        elif extensao in TIPOS_EXTENSAO:
            resultado += "Identificação: baseada na extensão do arquivo."
        else:
            resultado += "Não foi possível identificar o tipo."

        return resultado

    except FileNotFoundError:
        return "Erro: o arquivo não foi encontrado."
    except PermissionError:
        return "Erro: não foi possível acessar o arquivo."
    except OSError as erro:
        return f"Erro ao analisar o arquivo: {erro}"

def obter_dados_brutos(caminho):
        """Retorna apenas os dados (tipo e categoria) para ser usada em codigo"""
        tipo_conteudo = identificar_por_conteudo(caminho)
        if tipo_conteudo:
            return tipo_conteudo

        extensao = os.path.splitext(caminho)[1].lower()
        if extensao in TIPOS_EXTENSAO:
            return TIPOS_EXTENSAO[extensao]
        return ("Desconhecido", "Desconhecida")