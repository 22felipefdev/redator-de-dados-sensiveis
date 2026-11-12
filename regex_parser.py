import re

PADRAO_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
PADRAO_CPF = re.compile(
    r"(?<![0-9])(?:[0-9]{11}|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2})(?![0-9])"
)


def normalizar_digitos(valor: str) -> str:
    return re.sub(r"[^0-9]", "", valor)


def validar_cpf(valor: str) -> bool:
    cpf = normalizar_digitos(valor)

    # caso seja diferente de 11 digitos ou sequencias repetidas
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(
            int(cpf[posicao]) * (tamanho + 1 - posicao)
            for posicao in range(tamanho)
        )
        resto = soma % 11
        digito_calculado = 0 if resto < 2 else 11 - resto

        if digito_calculado != int(cpf[tamanho]):
            return False
    return True


def extrair_cpfs_validos(texto: str) -> list[str]:
    candidatos = PADRAO_CPF.findall(texto)

    return list(dict.fromkeys(
        cpf for cpf in candidatos if validar_cpf(cpf)
    ))


def extrair_emails(texto: str) -> list[str]:
    return list(dict.fromkeys(PADRAO_EMAIL.findall(texto)))


def extrair_evidencias(texto: str):
    return {
        "emails": extrair_emails(texto),
        "cartoes_credito_validados": [],
        "numeros_de_oficio": [],
        "cpfs_validos": extrair_cpfs_validos(texto),
        "cnpjs_validos": [],
        "rgs_rotulados": [],
    }
