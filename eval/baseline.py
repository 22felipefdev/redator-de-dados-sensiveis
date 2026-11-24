"""Baseline de avaliação do scanner.

Pode ser executado de qualquer diretório:

    python eval/baseline.py
    python eval/baseline.py --diagnostico            # detalha perdas e FPs
    python eval/baseline.py -d --tipo EMAIL          # filtra o diagnóstico

O corpus fica em eval/corpus. Para cada imagem (png/jpg/jpeg) deve existir um
JSON de verdade com o mesmo nome/base. O texto do OCR é cacheado com um sufixo
que contém o hash de ocr.py: se o pré-processamento mudar, o cache é refeito.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import argparse
import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher

from ocr import extrair_texto
from regex_parser import (extrair_evidencias, normalizar_digitos,
                          normalizar_codigo, normalizar_cnpj, PADRAO_RG,
                          extrair_emails_reparados, remover_colisoes)
from presidio_detector import analisar_texto

NORM = {
    "CPF": normalizar_digitos, "CARTAO": normalizar_digitos,
    "CNPJ": normalizar_cnpj, "RG": normalizar_codigo,
    "EMAIL": lambda v: v.strip().casefold(),
}
CHAVE_REGEX = {"CPF": "cpfs_validos", "CNPJ": "cnpjs_validos",
               "CARTAO": "cartoes_credito_validados",
               "EMAIL": "emails", "RG": "rgs_rotulados"}
ENT_PRESIDIO = {"BR_CPF": "CPF", "BR_CNPJ": "CNPJ", "BR_CARTAO": "CARTAO",
                "EMAIL_ADDRESS": "EMAIL", "BR_RG": "RG"}
ROTULOS = {
    "CPF": ("cpf", "contribuinte", "pessoa fisica", "pessoa física"),
    "CNPJ": ("cnpj", "inscricao", "inscrição", "empresa", "juridica", "jurídica"),
    "CARTAO": ("cartao", "cartão", "visa", "master", "elo", "amex",
               "credito", "crédito"),
    "EMAIL": ("email", "e-mail", "correio", "contato"),
    "RG": ("rg", "registro", "identidade"),
}

CORPUS = Path(__file__).resolve().parent / "corpus"
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg"}
VERSAO_OCR = hashlib.sha1((RAIZ / "ocr.py").read_bytes()).hexdigest()[:8]


def arquivos_corpus() -> list[Path]:
    """Lista o corpus aceitando qualquer caixa na extensão."""
    return sorted(
        arquivo for arquivo in CORPUS.iterdir()
        if arquivo.is_file() and arquivo.suffix.lower() in EXTENSOES_IMAGEM
    )


def ler_texto(img: Path) -> str:
    """Cache versionado pelo código do OCR e pelo arquivo de imagem."""
    chave = f"{VERSAO_OCR}-{img.stat().st_mtime_ns}-{img.stat().st_size}"
    cache = img.with_suffix(f".ocr-{chave}.txt")
    if cache.exists():
        return cache.read_text(encoding="utf-8")

    texto = extrair_texto(img)
    cache.write_text(texto, encoding="utf-8")
    return texto


def blocos(texto: str) -> list[str]:
    """Quebra o OCR em blocos para não colar dígitos de linhas/colunas distintas.

    A quebra em 2+ espaços preserva números que o OCR escreveu dígito a dígito
    ('1 1 4 4 ...'), mas impede que o cabeçalho '[Página 1]' ou outra coluna
    entre no mesmo bloco.
    """
    return [
        bloco
        for linha in texto.splitlines()
        for bloco in re.split(r"[ \t]{2,}", linha)
    ]


def ocr_leu_normalizado(alvo: str, tipo: str, texto: str) -> bool:
    if not alvo:
        return False
    return any(alvo in NORM[tipo](bloco) for bloco in blocos(texto))


def ocr_leu(valor: str, tipo: str, texto: str) -> bool:
    """Verdadeiro se o valor esperado foi lido pelo OCR, dentro de um bloco.

    Diferente da versão original, não normaliza o texto inteiro: normalizar
    tudo colava a pontuação removida e fazia '529.982. 247-25' parecer leitura
    perfeita mesmo quando a regex não encontrava nada.
    """
    return ocr_leu_normalizado(NORM[tipo](valor), tipo, texto)


def carregar_verdade(img: Path) -> tuple[set, dict]:
    caminho = img.with_suffix(".json")
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    reais, brutos = set(), {}
    for item in dados:
        tipo = item["tipo"]
        if tipo not in NORM:
            raise ValueError(f"{caminho.name}: tipo desconhecido {tipo!r}")
        chave = (tipo, NORM[tipo](item["valor"]))
        reais.add(chave)
        brutos.setdefault(chave, item["valor"])
    return reais, brutos


def previstos_regex(texto: str) -> tuple[set, dict]:
    evidencias = extrair_evidencias(texto)
    achados, brutos = set(), {}
    for tipo, chave_evidencia in CHAVE_REGEX.items():
        for valor in evidencias[chave_evidencia]:
            chave = (tipo, NORM[tipo](valor))
            achados.add(chave)
            brutos.setdefault(chave, valor)
    for email in extrair_emails_reparados(texto):
        chave = ("EMAIL", NORM["EMAIL"](email["valor"]))
        achados.add(chave)
        brutos.setdefault(chave, email["valor"])
    return achados, brutos


def previstos_presidio(texto: str) -> tuple[set, dict]:
    achados, brutos = set(), {}
    for resultado in analisar_texto(texto):
        tipo = ENT_PRESIDIO.get(resultado.entity_type)
        if not tipo:
            continue
        trecho = texto[resultado.start:resultado.end]
        if tipo == "RG" and (m := PADRAO_RG.search(trecho)):
            trecho = m.group(1)
        chave = (tipo, NORM[tipo](trecho))
        achados.add(chave)
        brutos.setdefault(chave, trecho)
    return achados, brutos


def linhas_relevantes(texto: str, tipo: str, alvo: str,
                      limite: int = 2) -> list[tuple[int, int, str]]:
    """Linhas do OCR com maior sobreposição com o valor normalizado.

    É uma heurística de localização, não uma prova: mostra onde procurar no
    texto OCR. Quando não há sobreposição razoável, usa as linhas com rótulo
    do tipo (cpf, cnpj, e-mail, ...).
    """
    pontuados = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        bruta = linha.strip()
        if not bruta:
            continue
        tamanho = SequenceMatcher(
            None, alvo, NORM[tipo](bruta), autojunk=False
        ).find_longest_match().size
        if tamanho >= min(4, len(alvo)):
            pontuados.append((tamanho, numero, bruta[:160]))
    if pontuados:
        return sorted(pontuados, key=lambda item: (-item[0], item[1]))[:limite]

    rotulos = ROTULOS.get(tipo, ())
    return [
        (0, numero, linha.strip()[:160])
        for numero, linha in enumerate(texto.splitlines(), start=1)
        if any(rotulo in linha.casefold() for rotulo in rotulos)
    ][:limite]


def _sim(condicao: bool) -> str:
    return "sim" if condicao else "não"


def diagnosticar(img: Path, texto: str, reais: set, brutos_reais: dict,
                 regex: set, brutos_regex: dict, presidio: set,
                 brutos_presidio: dict, sistema: set, reparados: set,
                 tipo_filtro: str | None = None) -> None:
    """Mostra perdas reais e FPs com as linhas de OCR que os originaram."""
    print("\n" + "=" * 78)
    print(f"DIAGNÓSTICO — {img.name}")
    print("=" * 78)

    perdas = [
        chave for chave in sorted(reais)
        if chave not in sistema
        and (tipo_filtro is None or chave[0] == tipo_filtro)
    ]
    print(f"\nPERDAS DO SISTEMA ({len(perdas)}):")
    if not perdas:
        print("  nenhuma")
    for tipo, valor in perdas:
        chave = (tipo, valor)
        print(f"  [{tipo}] esperado: {brutos_reais.get(chave, valor)}")
        print(f"    OCR lido: {_sim(ocr_leu_normalizado(valor, tipo, texto))}"
              f" | regex: {_sim(chave in regex)}"
              f" | presidio: {_sim(chave in presidio)}")
        for tamanho, numero, linha in linhas_relevantes(texto, tipo, valor):
            print(f"    linha {numero} (sobreposição {tamanho}): {linha}")

    aceitos = [
        chave for chave in sorted(reparados & sistema)
        if tipo_filtro is None or chave[0] == tipo_filtro
    ]
    print(f"\nREPAROS ACEITOS ({len(aceitos)}):")
    if not aceitos:
        print("  nenhum")
    for _, valor in aceitos:
        print(f"  {valor}  (marcado para revisão)")

    print("\nFALSOS POSITIVOS:")
    for nome, previstos, brutos in (
        ("regex", regex, brutos_regex),
        ("presidio", presidio, brutos_presidio),
    ):
        fps = [
            chave for chave in sorted(previstos)
            if chave not in reais
            and (tipo_filtro is None or chave[0] == tipo_filtro)
        ]
        print(f"  {nome}: {len(fps)}")
        for tipo, valor in fps:
            chave = (tipo, valor)
            print(f"    [{tipo}] previsto: {brutos.get(chave, valor)}"
                  f"  (normalizado: {valor})")
            for tamanho, numero, linha in linhas_relevantes(texto, tipo, valor):
                print(f"      linha {numero} (sobreposição {tamanho}): {linha}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-d", "--diagnostico", action="store_true",
                        help="mostra perdas e falsos positivos por amostra")
    parser.add_argument("--tipo", metavar="TIPO",
                        help="filtra o diagnóstico (ex.: EMAIL, CNPJ)")
    args = parser.parse_args()

    if not CORPUS.is_dir():
        sys.exit(f"Corpus não encontrado: {CORPUS}")

    c = defaultdict(lambda: defaultdict(int))

    for img in arquivos_corpus():
        variante = "limpo" if "limpo" in img.name.lower() else "ruidoso"
        reais, brutos_reais = carregar_verdade(img)
        texto = ler_texto(img)

        regex, brutos_regex = previstos_regex(texto)
        presidio, brutos_presidio = previstos_presidio(texto)
        regex = remover_colisoes(regex)
        presidio = remover_colisoes(presidio)
        reparados = {
            ("EMAIL", NORM["EMAIL"](email["valor"]))
            for email in extrair_emails_reparados(texto)
        }
        # Espelha detector.cruzar_evidencias(): interseção dos detectores mais
        # os reparos marcados para revisão, que não dependem do Presidio.
        sistema = (regex & presidio) | reparados

        if args.diagnostico:
            diagnosticar(img, texto, reais, brutos_reais,
                         regex, brutos_regex, presidio, brutos_presidio,
                         sistema, reparados, args.tipo)

        for tipo, valor in reais:
            m = c[(variante, tipo)]
            m["total"] += 1
            m["ocr_ok"] += ocr_leu_normalizado(valor, tipo, texto)

        for nome, previstos in (("regex", regex), ("presidio", presidio),
                                ("sistema", sistema)):
            for tipo in NORM:
                p = {x for x in previstos if x[0] == tipo}
                r = {x for x in reais if x[0] == tipo}
                c[(variante, tipo)][f"{nome}_tp"] += len(p & r)
                c[(variante, tipo)][f"{nome}_fp"] += len(p - r)

    print(f"\n{'variante':8} {'tipo':7} {'OCR leu':>8} {'regex rec':>10} "
          f"{'regex FP':>9} {'pres rec':>9} {'pres FP':>8} "
          f"{'sist rec':>9} {'sist FP':>8}")
    for (variante, tipo), m in sorted(c.items()):
        total = m["total"] or 1
        print(f"{variante:8} {tipo:7} {m['ocr_ok']/total:8.0%} "
              f"{m['regex_tp']/total:10.0%} {m['regex_fp']:9d} "
              f"{m['presidio_tp']/total:9.0%} {m['presidio_fp']:8d} "
              f"{m['sistema_tp']/total:9.0%} {m['sistema_fp']:8d}")

    soma = defaultdict(int)
    for m in c.values():
        for chave, valor in m.items():
            soma[chave] += valor
    total = soma["total"] or 1
    print("-" * 87)
    print(f"{'TOTAL':8} {'':7} {soma['ocr_ok']/total:8.0%} "
          f"{soma['regex_tp']/total:10.0%} {soma['regex_fp']:9d} "
          f"{soma['presidio_tp']/total:9.0%} {soma['presidio_fp']:8d} "
          f"{soma['sistema_tp']/total:9.0%} {soma['sistema_fp']:8d}")


if __name__ == "__main__":
    main()
