from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

from regex_parser import *

config = {
    "nlp_engine_name": "spacy",
    "models": [
        {"lang_code": "pt", "model_name": "pt_core_news_sm"},
    ]
}
provedor_nlp = NlpEngineProvider(nlp_configuration=config)
motor_nlp = provedor_nlp.create_engine()

analisador = AnalyzerEngine(
    nlp_engine=motor_nlp,
    supported_languages=["pt", "en"],
)

reconhecedor_email = PatternRecognizer(
    supported_entity="EMAIL_ADDRESS",
    supported_language="pt",
    patterns=[
        Pattern(
            name="email",
            regex=PADRAO_EMAIL.pattern,
            score=0.85,
        )
    ],
    context=["email", "e-mail", "correio", "contato"],
)
analisador.registry.add_recognizer(reconhecedor_email)

reconhecedor_cpf = PatternRecognizer(
    supported_entity="BR_CPF",
    supported_language="pt",
    patterns=[
        Pattern(
            name="cpf",
            regex=PADRAO_CPF.pattern,
            score=0.5,
        )
    ],
    context=["cpf", "pessoa", "fisica", "física", "contribuinte"],
)
analisador.registry.add_recognizer(reconhecedor_cpf)
reconhecedor_cnpj = PatternRecognizer(
    supported_entity="BR_CNPJ",
    supported_language="pt",
    patterns=[
        Pattern(
            name="cnpj",
            regex=PADRAO_CNPJ.pattern,
            score=0.5,
        )
    ],
    context=["cnpj", "empresa", "empresarial", "juridica", "jurídica", "inscricao", "inscrição"],
)
analisador.registry.add_recognizer(reconhecedor_cnpj)
reconhecedor_rg = PatternRecognizer(
    supported_entity="BR_RG",
    supported_language="pt",
    patterns=[
        Pattern(
            name="rg",
            regex=PADRAO_RG.pattern,
            score=0.5,
        )
    ],
    context=["rg", "identidade", "geral", "registro", "documento", "emissor"],
)
analisador.registry.add_recognizer(reconhecedor_rg)

reconhecedor_cartao = PatternRecognizer(
    supported_entity="BR_CARTAO",
    supported_language="pt",
    patterns=[
        Pattern(
            name="cartao",
            regex=PADRAO_CARTAO.pattern,
            score=1,
        )
    ],
    context=[
        "cartao", "cartão", "credito", "crédito",
        "visa", "mastercard", "master", "elo", "amex",
        "validade", "cvv", "titular",
    ],
)
analisador.registry.add_recognizer(reconhecedor_cartao)

reconhecedor_oficio = PatternRecognizer(
    supported_entity="BR_NUMERO_OFICIO",
    supported_language="pt",
    patterns=[
        Pattern(
            name="numero_oficio",
            regex=PADRAO_OFICIO.pattern,
            score=0.5,
        )
    ],
    context=["oficio", "ofício", "expediente", "correspondencia", "correspondência"],
)
analisador.registry.add_recognizer(reconhecedor_oficio)


def analisar_texto(texto: str):
    resultados = analisador.analyze(
        text=texto,
        language="pt",
        entities=[
            "EMAIL_ADDRESS",
            "BR_CPF",
            "BR_CNPJ",
            "BR_RG",
            "BR_CARTAO",
            "BR_NUMERO_OFICIO",
        ],
    )
    resultados_validos = []

    for resultado in resultados:
        trecho = texto[resultado.start:resultado.end]

        if resultado.entity_type == "BR_CPF" and not validar_cpf(trecho):
            continue

        if resultado.entity_type == "BR_CNPJ" and not validar_cnpj(trecho):
            continue

        if resultado.entity_type == "BR_CARTAO" and not validar_luhn(trecho):
            continue

        resultados_validos.append(resultado)

    return resultados_validos
