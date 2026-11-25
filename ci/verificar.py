r"""Gate único de verificação: testes, sintaxe, baseline, front e vulnerabilidades.

Uso:
    python ci/verificar.py --exigir-baseline       # front em web/
    python ci/verificar.py --web <outro-front>     # caminho alternativo

O front vive em web/ neste monorepo. Use --web (ou WEB_DIR) apenas para apontar
para outra pasta. Com --container os testes da API rodam dentro do container,
útil quando o Python local não tem FastAPI.

O corpus é dado do cliente e não é versionado. Sem ele o baseline é avisado e
pulado; use --exigir-baseline quando o corpus estiver disponível no runner.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# No Windows o console padrão é cp1252 e não imprime ✓ do npm.
for fluxo in (sys.stdout, sys.stderr):
    if hasattr(fluxo, "reconfigure"):
        fluxo.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "eval" / "corpus"
WEB_PADRAO = RAIZ / "web"

RECALL_MINIMO = 99
FP_MAXIMO = 2
PADRAO_TOTAL = re.compile(
    r"TOTAL\s+(\d+)%\s+(\d+)%\s+(\d+)\s+(\d+)%\s+(\d+)\s+(\d+)%\s+(\d+)"
)


def executar(comando, diretorio, nome, env=None):
    """Executa um comando e falha o gate se ele retornar diferente de zero."""
    print(f"\n== {nome} ==")
    visivel = " ".join(str(parte) for parte in comando)
    print(visivel)
    resultado = subprocess.run(
        comando,
        cwd=diretorio,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if resultado.stdout.strip():
        print(resultado.stdout.strip())
    if resultado.returncode != 0:
        if resultado.stderr.strip():
            print(resultado.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"FALHOU: {nome}")
    return resultado.stdout


def python_padrao():
    virtual = RAIZ / ".venv"
    if os.name == "nt":
        candidato = virtual / "Scripts" / "python.exe"
    else:
        candidato = virtual / "bin" / "python"
    return str(candidato) if candidato.exists() else sys.executable


def verificar_python(python, container=None):
    arquivos = [
        "api.py",
        "detector.py",
        "ocr.py",
        "ocr_posicoes.py",
        "presidio_detector.py",
        "regex_parser.py",
        "test_api.py",
        "eval/baseline.py",
        "ci/verificar.py",
        "ci/test_baseline.py",
        "ci/test_verificar.py",
        "ci/test_lock.py",
        "ci/test_workflows.py",
    ]
    executar([python, "-m", "py_compile", *arquivos], RAIZ, "sintaxe Python")
    executar(
        [
            python,
            "-m",
            "unittest",
            "-v",
            "ci.test_baseline",
            "ci.test_verificar",
            "ci.test_lock",
            "ci.test_workflows",
        ],
        RAIZ,
        "testes do gate, do lock e dos workflows",
    )

    if container:
        comando_testes = [
            "docker",
            "exec",
            "-i",
            container,
            "python",
            "-m",
            "unittest",
            "-v",
            "test_api",
        ]
    else:
        comando_testes = [python, "-m", "unittest", "-v", "test_api"]
    executar(comando_testes, RAIZ, "testes da API")


def verificar_baseline(python, exigir):
    if not CORPUS.is_dir():
        aviso = "baseline ignorado: eval/corpus não está disponível"
        if exigir:
            raise SystemExit(f"FALHOU: {aviso}")
        print(f"\nAVISO: {aviso}")
        return

    ambiente = os.environ.copy()
    # No Linux o Tesseract vem do PATH (apt no CI); no Windows, se não estiver
    # no PATH, usamos o caminho de instalação padrão.
    if os.name == "nt" and not shutil.which("tesseract"):
        ambiente.setdefault(
            "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
    saida = executar(
        [python, "eval/baseline.py"], RAIZ, "baseline de recall", ambiente
    )
    encontrado = PADRAO_TOTAL.search(saida)
    if not encontrado:
        raise SystemExit("FALHOU: não foi possível ler a linha TOTAL do baseline")

    recall = int(encontrado.group(6))
    falsos_positivos = int(encontrado.group(7))
    print(f"\nsistema: recall={recall}% fp={falsos_positivos}")
    if recall < RECALL_MINIMO:
        raise SystemExit(
            f"FALHOU: recall {recall}% abaixo de {RECALL_MINIMO}%"
        )
    if falsos_positivos > FP_MAXIMO:
        raise SystemExit(
            f"FALHOU: {falsos_positivos} falsos positivos acima de {FP_MAXIMO}"
        )


def verificar_front(web):
    if not web:
        print("\nAVISO: front ignorado (use --web ou WEB_DIR)")
        return
    diretorio = Path(web).resolve()
    if not (diretorio / "package.json").is_file():
        raise SystemExit(f"FALHOU: package.json não encontrado em {diretorio}")
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("FALHOU: npm não encontrado no PATH")
    executar([npm, "run", "build"], diretorio, "build do front")
    executar([npm, "run", "lint"], diretorio, "lint do front")


def verificar_vulnerabilidades():
    pip_audit = shutil.which("pip-audit")
    if pip_audit:
        executar(
            [pip_audit, "-r", "requirements.lock.txt"], RAIZ, "pip-audit"
        )
    else:
        print("\nAVISO: pip-audit não instalado (instale no CI)")

    trivy = shutil.which("trivy")
    if not trivy:
        print("AVISO: trivy CLI não instalado (use a action no CI)")
        return
    docker = shutil.which("docker")
    if not docker:
        print("AVISO: docker não encontrado; trivy ignorado")
        return
    inspecao = subprocess.run(
        [docker, "image", "inspect", "redator-api:latest"],
        capture_output=True,
    )
    if inspecao.returncode != 0:
        print("AVISO: imagem redator-api:latest não existe; trivy ignorado")
        return
    executar(
        [
            trivy,
            "image",
            "--exit-code",
            "1",
            "--severity",
            "HIGH,CRITICAL",
            "redator-api:latest",
        ],
        RAIZ,
        "trivy (HIGH/CRITICAL)",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web", default=os.getenv("WEB_DIR") or str(WEB_PADRAO))
    parser.add_argument("--python", default=python_padrao())
    parser.add_argument("--exigir-baseline", action="store_true")
    parser.add_argument(
        "--container",
        default=os.getenv("API_CONTAINER"),
        help="Nome do container da API para rodar os testes (ex.: redator-api-1)",
    )
    argumentos = parser.parse_args()

    verificar_python(argumentos.python, argumentos.container)
    verificar_baseline(argumentos.python, argumentos.exigir_baseline)
    verificar_front(argumentos.web)
    verificar_vulnerabilidades()
    print("\nTODAS AS VERIFICAÇÕES PASSARAM")


if __name__ == "__main__":
    main()
