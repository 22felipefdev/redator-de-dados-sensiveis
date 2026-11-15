import re

PADRAO_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
PADRAO_CPF = re.compile(
    r"(?<![0-9])(?:[0-9]{11}|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2})(?![0-9])"
)
PADRAO_CNPJ = re.compile(
    r"(?<![A-Z0-9])(?:"
    r"[A-Z0-9]{12}[0-9]{2}|"
    r"[A-Z0-9]{2}\.[A-Z0-9]{3}\.[A-Z0-9]{3}/[A-Z0-9]{4}-[0-9]{2}"
    r")(?![A-Z0-9])",
    re.IGNORECASE,
)
PADRAO_RG = re.compile(
    r"(?im)\b(?:rg|registro[ \t]+geral|identidade|n[º°o.]?[ \t]*registro)\b"
    r"[ \t]*(?:n[º°o.]?[ \t]*)?[:#\-]?[ \t]*(?:\r?\n[ \t]*)?"
    r"([A-Z0-9][A-Z0-9./\-]{4,19})(?![A-Z0-9])"
)
PADRAO_CARTAO = re.compile(
    r"(?<![0-9])(?:[0-9][ \t.-]?){12,18}[0-9](?![0-9])"
)
CONTEXTO_CARTAO = re.compile(
    r"cart[aã]o|visa|master\s*card|mastercard|elo|amex|american\s+express",
    re.IGNORECASE,
)
PADRAO_OFICIO = re.compile(
    r"\bof[ií]cio\b[ \t]*"
    r"(?:n[º°o.]?[ \t]*)?"
    r"(?:n[uú]mero[ \t]*)?"
    r"[:#\-]?[ \t]*(?:\r?\n[ \t]*)?"
    r"([A-Z0-9][A-Z0-9./\-]{1,30})",
    re.IGNORECASE,
)


def normalizar_digitos(valor: str) -> str:
    return re.sub(r"[^0-9]", "", valor)


def normalizar_codigo(valor: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", valor.upper())


def normalizar_cnpj(valor: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", valor.upper())


def calcular_digito_cnpj(base: str, pesos: tuple[int, ...]) -> str:
    soma = sum(
        (ord(caractere) - 48) * peso
        for caractere, peso in zip(base, pesos)
    )
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def validar_cnpj(valor: str) -> bool:
    cnpj = normalizar_cnpj(valor)

    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    pesos_primeiro_digito = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    pesos_segundo_digito = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

    primeiro = calcular_digito_cnpj(
        cnpj[:12], pesos_primeiro_digito
    )
    segundo = calcular_digito_cnpj(
        cnpj[:12] + primeiro, pesos_segundo_digito
    )

    return cnpj[-2:] == primeiro + segundo


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


def validar_luhn(numeros: str) -> bool:
    digitos = normalizar_digitos(numeros)

    if not 13 <= len(digitos) <= 19 or len(set(digitos)) == 1:
        return False
    soma = 0
    for posicao, caractere in enumerate(reversed(digitos)):
        digito = int(caractere)

        if posicao % 2 == 1:
            digito *= 2
            if digito > 9:
                digito -= 9
        soma += digito
    return soma % 10 == 0


def extrair_rgs_rotulados(texto: str) -> list[str]:
    candidatos = PADRAO_RG.findall(texto)
    return list(dict.fromkeys(candidatos))


def extrair_cpfs_validos(texto: str) -> list[str]:
    candidatos = PADRAO_CPF.findall(texto)

    return list(dict.fromkeys(
        cpf for cpf in candidatos if validar_cpf(cpf)
    ))


def extrair_cnpjs_validos(texto: str) -> list[str]:
    candidatos = PADRAO_CNPJ.findall(texto)

    return list(dict.fromkeys(
        cnpj for cnpj in candidatos if validar_cnpj(cnpj)
    ))


def extrair_emails(texto: str) -> list[str]:
    return list(dict.fromkeys(PADRAO_EMAIL.findall(texto)))


def extrair_numeros_oficio(texto: str) -> list[str]:
    numeros = PADRAO_OFICIO.findall(texto)
    return list(dict.fromkeys(numero.strip() for numero in numeros))


def extrair_cartoes_validos(texto: str) -> list[str]:
    cartoes = []

    for ocorrencia in PADRAO_CARTAO.finditer(texto):
        candidato = ocorrencia.group(0)

        inicio = max(0, ocorrencia.start() - 60)
        fim = min(len(texto), ocorrencia.end() + 60)
        contexto = texto[inicio:fim]

        if CONTEXTO_CARTAO.search(contexto) and validar_luhn(candidato):
            cartoes.append(candidato)

    return list(dict.fromkeys(cartoes))


def extrair_evidencias(texto: str):
    return {
        "emails": extrair_emails(texto),
        "cartoes_credito_validados": extrair_cartoes_validos(texto),
        "numeros_de_oficio": extrair_numeros_oficio(texto),
        "cpfs_validos": extrair_cpfs_validos(texto),
        "cnpjs_validos": extrair_cnpjs_validos(texto),
        "rgs_rotulados": extrair_rgs_rotulados(texto),
    }
