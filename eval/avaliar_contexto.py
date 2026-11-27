r"""Avalia as sugestões contextuais contra o corpus sintético.

Execução:
    .\.venv\Scripts\python.exe eval/avaliar_contexto.py --modo mock
    .\.venv\Scripts\python.exe eval/avaliar_contexto.py --modo live

``mock`` testa o encanamento (índices, validação, métricas) sem rede.
``live`` chama o modelo real; os números variam e nunca entram no gate do CI.
"""
import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from conhecimento_lgpd import carregar
from regex_parser import extrair_evidencias

CAMINHO_PADRAO = RAIZ / "eval" / "corpus" / "contextos.jsonl"
CONFIANCA_MINIMA = 0.75


def carregar_corpus(caminho: Path) -> list[dict]:
    casos = []
    for numero, linha in enumerate(
        caminho.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not linha.strip():
            continue
        caso = json.loads(linha)
        if "id" not in caso or "texto" not in caso or "esperado" not in caso:
            raise ValueError(f"Linha {numero} incompleta em {caminho}")
        casos.append(caso)
    return casos


def com_indices(caso: dict) -> list[dict]:
    """Índices são calculados, nunca digitados à mão."""
    resultado = []
    for item in caso["esperado"]:
        inicio = caso["texto"].index(item["trecho"])
        resultado.append(
            {
                "trecho": item["trecho"],
                "inicio": inicio,
                "fim": inicio + len(item["trecho"]),
                "categoria": item["categoria"],
                "contexto_presidio": re.findall(r"\w+", caso["texto"])[:3],
                "confianca": 0.9,
            }
        )
    return resultado


def prever(caso: dict, modo: str) -> list[dict]:
    if modo == "mock":
        return com_indices(caso)
    from ia_contexto import sugerir_dados_sensiveis

    return sugerir_dados_sensiveis(caso["texto"])


def valores_deterministicos(texto: str) -> set[str]:
    """Valores que regex/Presidio já decidem: a IA não deve sugerir nenhum."""
    valores = set()
    for itens in extrair_evidencias(texto).values():
        for item in itens:
            if isinstance(item, str):
                valores.add(item)
            elif isinstance(item, dict):
                for valor in item.values():
                    if isinstance(valor, str):
                        valores.add(valor)
    return valores


def avaliar(casos: list[dict], modo: str) -> dict:
    categorias = set(carregar().get("categorias", {}))
    esperados = 0
    acertados = 0
    falsos_positivos = 0
    proibidos = 0
    invalidos = 0
    detalhes = []

    for caso in casos:
        texto = caso["texto"]
        alvos = {item["trecho"] for item in caso["esperado"]}
        sugestoes = prever(caso, modo)
        detectados = {item["trecho"] for item in sugestoes}
        determinados = valores_deterministicos(texto)

        esperados += len(alvos)
        acertados += len(alvos & detectados)

        for sugestao in sugestoes:
            trecho = sugestao.get("trecho", "")
            if trecho not in alvos:
                falsos_positivos += 1
                detalhes.append(f"{caso['id']}: falso positivo {trecho!r}")
            if any(valor and valor in trecho for valor in determinados):
                proibidos += 1
                detalhes.append(f"{caso['id']}: sugestão de dado determinístico {trecho!r}")

            inicio = sugestao.get("inicio")
            fim = sugestao.get("fim")
            problema = None
            if not isinstance(inicio, int) or not isinstance(fim, int):
                problema = "índices ausentes"
            elif inicio >= fim or fim > len(texto) or texto[inicio:fim] != trecho:
                problema = "trecho não é cópia literal"
            elif sugestao.get("categoria") not in categorias:
                problema = "categoria fora do enum"
            elif sugestao.get("confianca", 0) < CONFIANCA_MINIMA:
                problema = "confiança abaixo do mínimo"
            elif not (
                1 <= len(sugestao.get("contexto_presidio", [])) <= 4
            ) or any(
                palavra not in texto
                for palavra in sugestao.get("contexto_presidio", [])
            ):
                problema = "contexto_presidio fora do documento"
            if problema:
                invalidos += 1
                detalhes.append(f"{caso['id']}: {problema} em {trecho!r}")

    recall = round(100 * acertados / esperados, 2) if esperados else 100.0
    return {
        "modo": modo,
        "casos": len(casos),
        "esperados": esperados,
        "acertados": acertados,
        "recall": recall,
        "falsos_positivos": falsos_positivos,
        "proibidos": proibidos,
        "invalidos": invalidos,
        "detalhes": detalhes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modo", choices=("mock", "live"), default="mock")
    parser.add_argument("--corpus", type=Path, default=CAMINHO_PADRAO)
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="avalia só os N primeiros casos (útil no modo live)",
    )
    parser.add_argument(
        "--exigir",
        action="store_true",
        help="sai com erro se recall < 100, FP > 0, proibidos > 0 ou inválidos > 0",
    )
    args = parser.parse_args()

    casos = carregar_corpus(args.corpus)
    if args.limite:
        casos = casos[: args.limite]
    resultado = avaliar(casos, args.modo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    if args.exigir and (
        resultado["recall"] < 100
        or resultado["falsos_positivos"]
        or resultado["proibidos"]
        or resultado["invalidos"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
