from dataclasses import dataclass, field

from regex_parser import *


# Tipos fixos: a classificação não depende mais de modelo externo. A ordem
# também define a ordem de apresentação no relatório.
TIPOS_E_RISCOS = (
    ("cpfs_validos", "CPF", "alto"),
    ("cnpjs_validos", "CNPJ", "alto"),
    ("cartoes_credito_validados", "Cartão de crédito", "alto"),
    ("rgs_rotulados", "RG", "alto"),
    ("emails", "E-mail", "medio"),
    ("numeros_de_oficio", "Número de ofício", "baixo"),
)


@dataclass
class ItemSensivel:
    dado: str
    tipo: str
    risco: str
    revisar: bool = False
    # Texto exatamente como o OCR leu. A interface usa para localizar o trecho
    # no PDF e cobri-lo, já que o valor reparado pode não existir no documento.
    original: str | None = None


@dataclass
class Relatorio:
    itens: list[ItemSensivel] = field(default_factory=list)


def cruzar_evidencias(texto, evidencias_regex, resultados_presidio):
    configuracao = {
        "EMAIL_ADDRESS": ("emails", lambda v: v.strip().casefold()),
        "BR_CPF": ("cpfs_validos", normalizar_digitos),
        "BR_CNPJ": ("cnpjs_validos", normalizar_cnpj),
        "BR_RG": ("rgs_rotulados", normalizar_codigo),
        "BR_CARTAO": ("cartoes_credito_validados", normalizar_digitos),
        "BR_NUMERO_OFICIO": (
            "numeros_de_oficio",
            lambda v: v.strip().casefold(),
        ),
    }
    encontrados_presidio = {}
    for resultado in resultados_presidio:
        if resultado.entity_type not in configuracao:
            continue

        trecho = texto[resultado.start:resultado.end]

        if resultado.entity_type == "BR_RG":
            correspondencia = PADRAO_RG.search(trecho)
            if correspondencia:
                trecho = correspondencia.group(1)

        elif resultado.entity_type == "BR_NUMERO_OFICIO":
            correspondencia = PADRAO_OFICIO.search(trecho)
            if correspondencia:
                trecho = correspondencia.group(1)

        _, normalizar = configuracao[resultado.entity_type]
        encontrados_presidio.setdefault(
            resultado.entity_type, set()
        ).add(normalizar(trecho)
              )
    confirmadas = {}

    for entidade, (chave_regex, normalizar) in configuracao.items():
        valores_presidio = encontrados_presidio.get(entidade, set())

        confirmadas[chave_regex] = [
            valor
            for valor in evidencias_regex.get(chave_regex, [])
            if normalizar(valor) in valores_presidio
        ]

    # O CPF passa por validação de dígitos verificadores; o RG depende só do
    # rótulo. Se o OCR associar o rótulo RG ao mesmo CPF, manter os dois
    # contaria o dado duas vezes. O CPF prevalece.
    cpfs = {normalizar_digitos(v) for v in confirmadas.get("cpfs_validos", [])}
    confirmadas["rgs_rotulados"] = [
        valor
        for valor in confirmadas.get("rgs_rotulados", [])
        if normalizar_digitos(valor) not in cpfs
    ]

    cnpjs = {normalizar_cnpj(v) for v in confirmadas.get("cnpjs_validos", [])}
    confirmadas["cartoes_credito_validados"] = [
        valor for valor in confirmadas.get("cartoes_credito_validados", [])
        if normalizar_digitos(valor) not in cnpjs
    ]
    # E-mails reparados não têm '@' no OCR: não dependem do Presidio.
    confirmadas["emails_reparados"] = [
        email["valor"]
        for email in evidencias_regex.get("emails_reparados", [])
        if email.get("revisar", True)
    ]

    return confirmadas


def identificar_dados_sensiveis(
        texto: str,
        evidencias_regex=None,
        resultados_presidio=None,
) -> Relatorio:
    """Monta o relatório só com o que a regex e o Presidio confirmaram.

    Nenhum valor é inferido: quando o OCR não leu o '@', o e-mail reparado
    entra com revisar=True para ser conferido por uma pessoa.
    """
    if evidencias_regex is None:
        evidencias_regex = extrair_evidencias(texto)

    if resultados_presidio is None:
        resultados_presidio = []

    confirmadas = cruzar_evidencias(
        texto,
        evidencias_regex,
        resultados_presidio,
    )

    grupos = TIPOS_E_RISCOS + (
        ("emails_reparados", "E-mail", "medio"),
    )
    relatorio = Relatorio()
    vistos = set()
    originais = {
        email["valor"]: email.get("original")
        for email in evidencias_regex.get("emails_reparados", [])
    }

    for chave, tipo, risco in grupos:
        revisar = chave == "emails_reparados"
        for valor in confirmadas.get(chave, []):
            dado = str(valor).strip()
            identificador = (tipo, dado.casefold())
            if not dado or identificador in vistos:
                continue
            vistos.add(identificador)
            relatorio.itens.append(
                ItemSensivel(
                    dado=dado,
                    tipo=tipo,
                    risco=risco,
                    revisar=revisar,
                    original=originais.get(dado) if revisar else None,
                )
            )

    return relatorio
