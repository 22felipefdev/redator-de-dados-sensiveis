r"""Verifica modelo em endpoint compatível com OpenAI sem gastar requisições à toa.

Sem flags: só consulta metadata (chave e catálogo) — zero inferência.
--ping: uma única chamada com `max_tokens=1` para testar roteamento/latência.
--real: uma única chamada com atestado sintético de ~84 palavras, medindo tempo.

Exemplos:
    .\.venv\Scripts\python.exe eval/verificar_modelo.py
    .\.venv\Scripts\python.exe eval/verificar_modelo.py --base-url https://generativelanguage.googleapis.com/v1beta/openai/ --modelo gemini-3.5-flash-lite
    .\.venv\Scripts\python.exe eval/verificar_modelo.py --modelo google/gemini-2.5-flash --ping
    .\.venv\Scripts\python.exe eval/verificar_modelo.py --modelo google/gemini-2.5-flash --real

A chave vem de IA_API_KEY (ou OPENROUTER_API_KEY, para compatibilidade).
"""
import argparse
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv
import httpx

load_dotenv(RAIZ / ".env")

import ia_contexto

TEXTO_TESTE = (
    "ATESTADO MEDICO\n\n"
    "Eu, Dr. Carlos Alberto Souza, CRM 12345, atesto que o paciente Jose da Silva, "
    "nascido em 12/05/1990, compareceu a consulta no dia 10/11/2026. Relata dor "
    "toracica persistente ha tres semanas, com diagnostico de hipertensao arterial "
    "e diabetes tipo 2. Em uso de metformina 850mg e losartana 50mg. Orientado a "
    "manter dieta, praticar atividade fisica e retornar em 30 dias. Nega tabagismo, "
    "etilismo e cirurgias anteriores. Exames laboratoriais demonstram glicemia "
    "elevada. Solicito acompanhamento nutricional e cardiologico. Este documento "
    "e valido por 60 dias."
)


def cabecalho(chave: str) -> dict:
    return {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}


def endpoint(base_url: str, caminho: str) -> str:
    """Evita barra dupla: a URL do Gemini já termina em '/'."""
    return f"{base_url.rstrip('/')}/{caminho.lstrip('/')}"


def avisar_chave(base_url: str, chave: str) -> None:
    """Avisa só quando o prefixo identifica claramente outro provedor."""
    if not chave:
        return

    conhecidos = ("sk-or", "AIza", "gsk_", "csk-")
    esperados = (
        ("generativelanguage.googleapis.com", ("AIza", "AQ"), "Google AI Studio")
        if "generativelanguage.googleapis.com" in base_url
        else ("api.groq.com", ("gsk_",), "Groq")
        if "api.groq.com" in base_url
        else ("api.cerebras.ai", ("csk-",), "Cerebras")
        if "api.cerebras.ai" in base_url
        else None
    )
    if not esperados:
        return

    _, prefixos, nome = esperados
    if not any(chave.startswith(p) for p in prefixos) and any(
        chave.startswith(p) for p in conhecidos
    ):
        print(f"AVISO= a chave parece ser de outro provedor; use uma chave da {nome}.")
        print("       defina IA_API_KEY=... no .env com a chave correta do provedor.")


def verificar_catalogo(base_url: str, modelo: str, chave: str) -> None:
    """Consulta /models quando disponível; não bloqueia o ping se não houver."""
    with httpx.Client(timeout=30) as cliente:
        try:
            catalogo = cliente.get(endpoint(base_url, "models"), headers=cabecalho(chave))
        except httpx.HTTPError as erro:
            print("CATALOGO=indisponível", type(erro).__name__)
            return

        if catalogo.status_code != 200:
            print("STATUS_CATALOGO=", catalogo.status_code)
            return

        itens = catalogo.json().get("data", [])
        encontrado = next(
            (
                item for item in itens
                if str(item.get("id", "")).rstrip("/").removeprefix("models/")
                == modelo.removeprefix("models/")
            ),
            None,
        )
        if not encontrado:
            print("MODELO_DISPONIVEL=NAO", modelo)
            return

        print("MODELO_DISPONIVEL=SIM")
        print("MODELO=", modelo)
        preco = encontrado.get("pricing", {}).get("prompt")
        if preco is not None:
            print("TIPO=", "gratuito" if str(preco) in ("0", "0.0") else f"pago ({preco})")
        else:
            print("TIPO=verificar no painel do provedor")
        contexto = encontrado.get("context_length") or encontrado.get("context_window")
        print("CONTEXTO=", contexto)


def verificar_conta_openrouter(base_url: str, chave: str) -> None:
    """Informações exclusivas do OpenRouter (zero inferência)."""
    with httpx.Client(timeout=30) as cliente:
        resposta = cliente.get(endpoint(base_url, "key"), headers=cabecalho(chave))
        if resposta.status_code != 200:
            print("STATUS_CHAVE=", resposta.status_code)
            return
        dados = resposta.json().get("data", {})
        print("CONTA_SEM_CREDITOS=", dados.get("is_free_tier"))
        print("CREDITOS_RESTANTES=", dados.get("limit_remaining"))
        print("COTA_GRATUITA=", dados.get("free_model_daily_requests"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default=ia_contexto.MODEL)
    parser.add_argument("--base-url", default=ia_contexto.BASE_URL)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--ping", action="store_true", help="1 chamada com max_tokens=1")
    grupo.add_argument("--real", action="store_true", help="1 chamada com atestado sintético")
    args = parser.parse_args()

    ia_contexto.BASE_URL = args.base_url
    chave = ia_contexto.chave_api()
    if not chave:
        print("IA_API_KEY / OPENROUTER_API_KEY ausente no .env")
        return 2

    avisar_chave(args.base_url, chave)
    if "openrouter.ai" in args.base_url:
        verificar_conta_openrouter(args.base_url, chave)
    verificar_catalogo(args.base_url, args.modelo, chave)

    if not (args.ping or args.real):
        print("INFERENCIA=0 (use --ping ou --real para gastar 1 requisição)")
        return 0

    inicio = time.perf_counter()
    try:
        with httpx.Client(timeout=60) as cliente:
            if args.ping:
                resposta = cliente.post(
                    endpoint(args.base_url, "chat/completions"),
                    headers=cabecalho(chave),
                    json={
                        "model": args.modelo,
                        "messages": [{"role": "user", "content": "Responda apenas: ok"}],
                        "max_tokens": 1,
                    },
                )
                print("PING_STATUS=", resposta.status_code)
                if resposta.status_code != 200:
                    print("ERRO=", resposta.text[:200])
                    print("RESET=", resposta.headers.get("x-ratelimit-reset"))
                    return 1
            else:
                ia_contexto.MODEL = args.modelo
                sugestoes = ia_contexto._consultar(TEXTO_TESTE, chave)
                print("SUGESTOES=", len(sugestoes))
                print("TRECHOS=", [item["trecho"] for item in sugestoes])
    except Exception as erro:
        print("ERRO=", type(erro).__name__, str(erro)[:500])
        causa = erro
        while causa.__cause__ is not None:
            causa = causa.__cause__
            resposta = getattr(causa, "response", None)
            if resposta is not None:
                print("CORPO_ERRO=", getattr(resposta, "text", "")[:500])
                break
        return 1

    print("SEGUNDOS=", round(time.perf_counter() - inicio, 1))
    print("INFERENCIA=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
