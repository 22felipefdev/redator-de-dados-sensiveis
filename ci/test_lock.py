r"""Testes do lock: toda dependência instalada precisa ter hash registrado."""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIRETO = RAIZ / "requirements.txt"
LOCK = RAIZ / "requirements.lock.txt"
HASH_MODELO = "sha256:c304fa04db3af73cd08a250feacf560506e15a2ec2469bd1b09f06847f6b455c"


def nome_pacote(linha):
    """Extrai o nome normalizado de uma linha de requisito."""
    encontrado = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", linha.strip())
    if not encontrado:
        return None
    return encontrado.group(1).lower().replace("_", "-").replace(".", "-")


class TesteLock(unittest.TestCase):
    def test_lock_existe(self):
        self.assertTrue(LOCK.is_file(), "requirements.lock.txt não encontrado")

    def test_todo_pacote_tem_hash(self):
        linhas = LOCK.read_text(encoding="utf-8").splitlines()
        for indice, linha in enumerate(linhas):
            if not linha.strip() or linha.lstrip().startswith(("#", "-")):
                continue
            if re.match(r"^[A-Za-z0-9]", linha):
                proximas = [item.strip() for item in linhas[indice + 1 : indice + 8]]
                self.assertTrue(
                    any("--hash=sha256:" in item for item in proximas),
                    f"sem hash logo após a linha {indice + 1}",
                )

    def test_diretos_estao_no_lock(self):
        conteudo = LOCK.read_text(encoding="utf-8")
        for linha in DIRETO.read_text(encoding="utf-8").splitlines():
            nome = nome_pacote(linha)
            if not nome:
                continue
            self.assertRegex(
                conteudo,
                rf"(?mi)^{re.escape(nome)}(?:\[[^\]]+\])?(?:==| @ )",
                f"{nome} ausente do lock",
            )

    def test_modelo_spacy_tem_hash_conhecido(self):
        self.assertIn(HASH_MODELO, LOCK.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
