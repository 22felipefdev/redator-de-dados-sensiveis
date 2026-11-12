import re

PADRAO_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)


def extrair_emails(texto: str) -> list[str]:
    return list(dict.fromkeys(PADRAO_EMAIL.findall(texto)))


def extrair_evidencias(texto: str):
    return {
        "emails": extrair_emails(texto),
        "cartoes_credito_validados": [],
        "numeros_de_oficio": [],
        "cpfs_validos": [],
        "cnpjs_validos": [],
        "rgs_rotulados": [],
    }
