"""Testes do gate: garante que uma regressão de recall realmente falha o CI."""
import unittest
from unittest.mock import patch

try:
    from . import verificar
except ImportError:  # execução direta do arquivo
    import verificar


class TesteBaseline(unittest.TestCase):
    def executar_com_linha(self, linha):
        with patch.object(verificar, "CORPUS") as corpus:
            corpus.is_dir.return_value = True
            with patch.object(verificar, "executar", return_value=linha):
                verificar.verificar_baseline("python", exigir=True)

    def test_linha_ok(self):
        self.executar_com_linha(
            "TOTAL 80% 99% 2 80% 0 99% 2"
        )

    def test_recall_baixo_falha(self):
        with self.assertRaises(SystemExit):
            self.executar_com_linha(
                "TOTAL 80% 98% 2 80% 0 98% 2"
            )

    def test_falsos_positivos_acima_do_limite_falha(self):
        with self.assertRaises(SystemExit):
            self.executar_com_linha(
                "TOTAL 80% 99% 2 80% 0 99% 3"
            )


if __name__ == "__main__":
    unittest.main()
