"""Garante que o baseline mede exatamente o que a API reporta."""
import unittest

from eval.baseline import previstos_sistema


class TesteBaselineEspelhaDetector(unittest.TestCase):
    def test_cpf_valido_nao_e_contado_como_rg(self):
        texto = "CPF: 678.085.841-26\nRG: 678.085.841-26"
        previstos = previstos_sistema(texto)
        self.assertIn(("CPF", "67808584126"), previstos)
        self.assertNotIn(("RG", "67808584126"), previstos)

    def test_rg_legitimo_continua_no_baseline(self):
        previstos = previstos_sistema("RG: 91.214.125-4")
        self.assertIn(("RG", "912141254"), previstos)


if __name__ == "__main__":
    unittest.main()
