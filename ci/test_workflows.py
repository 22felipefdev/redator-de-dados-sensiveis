r"""Testes dos workflows: YAML válido e ações fixadas por SHA."""
import re
import unittest
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
ACAO_FIXA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


class TesteWorkflows(unittest.TestCase):
    def test_workflows_existem(self):
        self.assertTrue(WORKFLOWS, "nenhum workflow encontrado")

    def test_yaml_valido(self):
        for caminho in WORKFLOWS:
            with self.subTest(arquivo=caminho.name):
                dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
                self.assertIsInstance(dados, dict)
                self.assertIn("jobs", dados)

    def test_acoes_fixadas_por_sha(self):
        for caminho in WORKFLOWS:
            dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
            for nome, trabalho in dados["jobs"].items():
                for passo in trabalho.get("steps", []):
                    uso = passo.get("uses")
                    if uso:
                        self.assertRegex(
                            uso,
                            ACAO_FIXA,
                            f"{caminho.name}/{nome}: ação móvel {uso}",
                        )


if __name__ == "__main__":
    unittest.main()
