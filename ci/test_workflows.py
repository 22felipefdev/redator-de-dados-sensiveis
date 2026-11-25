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

    def test_release_usa_front_do_monorepo(self):
        caminho = RAIZ / ".github" / "workflows" / "release.yml"
        conteudo = caminho.read_text(encoding="utf-8")
        self.assertNotIn("WEB_REPO", conteudo)
        self.assertNotIn("web_repo", conteudo)

        dados = yaml.safe_load(conteudo)
        web = dados["jobs"]["web"]
        self.assertNotIn("if", web)

        checkouts = [
            passo for passo in web["steps"]
            if str(passo.get("uses", "")).startswith("actions/checkout")
        ]
        self.assertEqual(len(checkouts), 1)
        self.assertNotIn("repository", checkouts[0].get("with", {}))

        builds = [
            passo for passo in web["steps"]
            if str(passo.get("uses", "")).startswith("docker/build-push-action")
        ]
        self.assertEqual(builds[0]["with"]["context"], "./web")
        self.assertEqual(builds[0]["with"]["file"], "./web/Dockerfile.prod")

    def test_release_publica_assets(self):
        conteudo = (RAIZ / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        dados = yaml.safe_load(conteudo)
        self.assertEqual(dados["jobs"]["publicar"]["needs"], ["api", "web"])
        for asset in (
            "sbom-api.spdx.json",
            "image-digests.env",
            "sbom-web.spdx.json",
            "image-web.env",
        ):
            self.assertIn(asset, conteudo)

    def test_ci_inclui_front_local(self):
        caminho = RAIZ / ".github" / "workflows" / "ci.yml"
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        passos = dados["jobs"]["verificar"]["steps"]
        comandos = [str(passo.get("run", "")) for passo in passos]
        self.assertTrue(any("npm ci --prefix web" in comando for comando in comandos))
        self.assertTrue(
            any(passo.get("env", {}).get("WEB_DIR") for passo in passos)
        )


if __name__ == "__main__":
    unittest.main()
