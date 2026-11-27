"""Testes da API. Execute: docker compose exec api python -m unittest -v test_api"""
import io
import os
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
import instructor

import api
import ia_contexto
import ocr_posicoes
from api import app

cliente = TestClient(app)


def imagem_com_cpf() -> bytes:
    try:
        fonte = ImageFont.truetype("DejaVuSans.ttf", 26)
    except OSError:
        fonte = ImageFont.load_default()

    imagem = Image.new("RGB", (900, 160), "white")
    desenho = ImageDraw.Draw(imagem)
    desenho.text((20, 30), "CPF: 123.456.789-09", font=fonte, fill="black")
    imagem = imagem.resize((1800, 320))

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


class TesteDetector(unittest.TestCase):
    def test_cpf_valido_nao_e_repetido_como_rg(self):
        texto = "CPF: 678.085.841-26\nRG: 678.085.841-26"
        relatorio = api.identificar_dados_sensiveis(
            texto, api.extrair_evidencias(texto), api.analisar_texto(texto)
        )
        itens = [(item.tipo, item.dado) for item in relatorio.itens]
        self.assertEqual(itens.count(("CPF", "678.085.841-26")), 1)
        self.assertNotIn(("RG", "678.085.841-26"), itens)

    def test_rg_legitimo_continua_sendo_detectado(self):
        texto = "RG: 91.214.125-4"
        relatorio = api.identificar_dados_sensiveis(
            texto, api.extrair_evidencias(texto), api.analisar_texto(texto)
        )
        self.assertIn(
            ("RG", "91.214.125-4"),
            [(item.tipo, item.dado) for item in relatorio.itens],
        )


class TesteSaude(unittest.TestCase):
    def test_saude(self):
        resposta = cliente.get("/api/saude")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok"})


class TesteAnalise(unittest.TestCase):
    def test_texto_valido(self):
        conteudo = b"CPF: 123.456.789-09\nEmail: joao.silva@example.com\n"
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("teste.txt", conteudo, "text/plain")},
        )
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["arquivo"], "teste.txt")
        # Texto bruto é PII: nunca deve sair da API.
        self.assertNotIn("texto", dados)
        self.assertIsNone(dados["posicoes"])
        tipos = [item["tipo"] for item in dados["itens"]]
        self.assertIn("CPF", tipos)
        self.assertIn("E-mail", tipos)

    def test_imagem_valida(self):
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("teste.png", imagem_com_cpf(), "image/png")},
        )
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["posicoes"]["palavras"])
        self.assertTrue(any(item["tipo"] == "CPF" for item in dados["itens"]))

    def test_extensao_invalida(self):
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("teste.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        self.assertEqual(resposta.status_code, 400)

    def test_assinatura_falsa(self):
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("falso.pdf", b"isto nao e um pdf", "application/pdf")},
        )
        self.assertEqual(resposta.status_code, 400)

    def test_arquivo_vazio(self):
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("vazio.txt", b"", "text/plain")},
        )
        self.assertEqual(resposta.status_code, 400)

    def test_acima_do_limite(self):
        conteudo = b"a" * (20 * 1024 * 1024 + 1)
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("grande.txt", conteudo, "text/plain")},
        )
        self.assertEqual(resposta.status_code, 413)

    def test_nome_sanitizado(self):
        conteudo = b"CPF: 123.456.789-09\n"
        resposta = cliente.post(
            "/api/analisar",
            files={"arquivo": ("../../etc/passwd.txt", conteudo, "text/plain")},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["arquivo"], "passwd.txt")

    def test_cache_por_conteudo(self):
        api._cache.clear()
        imagem = imagem_com_cpf()
        for _ in range(2):
            resposta = cliente.post(
                "/api/analisar",
                files={"arquivo": ("cache.png", imagem, "image/png")},
            )
            self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(api._cache), 1)
        api._cache.clear()

    def test_erro_generico_sem_vazamento(self):
        api._cache.clear()
        with patch.object(
            api, "analisar_imagem", side_effect=RuntimeError("caminho_secreto")
        ):
            resposta = cliente.post(
                "/api/analisar",
                files={"arquivo": ("erro.png", imagem_com_cpf(), "image/png")},
            )
        self.assertEqual(resposta.status_code, 500)
        self.assertNotIn("caminho_secreto", resposta.text)

    def test_limite_de_pixels(self):
        api._cache.clear()
        with patch.object(ocr_posicoes, "MAX_PIXELS", 10):
            resposta = cliente.post(
                "/api/analisar",
                files={"arquivo": ("grande.png", imagem_com_cpf(), "image/png")},
            )
        self.assertEqual(resposta.status_code, 500)
        self.assertNotIn("imagem grande", resposta.text)

    def test_fila_ocupada(self):
        with patch.object(api._limite_ocr, "acquire", return_value=False):
            resposta = cliente.post(
                "/api/analisar",
                files={
                    "arquivo": ("ocupado.txt", b"CPF: 123.456.789-09\n", "text/plain")
                },
            )
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.headers["Retry-After"], "5")

    def test_contrato_remove_campos_extras(self):
        api._cache.clear()
        with patch.object(
            api,
            "analisar_imagem",
            return_value={
                "texto": "CPF: 123.456.789-09",
                "posicoes": {
                    "largura": 10,
                    "altura": 10,
                    "palavras": [],
                    "campo_interno": "NAO_DEVE_SAIR",
                },
                "texto_interno": "NAO_DEVE_SAIR",
            },
        ):
            resposta = cliente.post(
                "/api/analisar",
                files={"arquivo": ("contrato.png", imagem_com_cpf(), "image/png")},
            )
        api._cache.clear()
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("NAO_DEVE_SAIR", resposta.text)

    def test_semaphore_liberado_apos_falha(self):
        api._cache.clear()
        with patch.object(api, "analisar_imagem", side_effect=RuntimeError("falha")):
            resposta = cliente.post(
                "/api/analisar",
                files={"arquivo": ("falha.png", imagem_com_cpf(), "image/png")},
            )
        self.assertEqual(resposta.status_code, 500)
        self.assertTrue(api._limite_ocr.acquire(blocking=False))
        api._limite_ocr.release()

    def test_contexto_desligado_por_padrao(self):
        resposta = cliente.post(
            "/api/analisar",
            files={
                "arquivo": (
                    "padrao.txt",
                    b"Paciente relatou diagnostico.\n",
                    "text/plain",
                )
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            all(item["origem"] == "deteccao" for item in resposta.json()["itens"])
        )

    def test_sugestao_da_ia_nao_vem_marcada(self):
        sugestoes = [
            {
                "trecho": "diagnóstico de diabetes",
                "inicio": 43,
                "fim": 66,
                "categoria": "SAUDE",
                "contexto_presidio": ["Paciente"],
                "confianca": 0.93,
            }
        ]
        with (
            patch.object(api, "IA_CONTEXTO", True),
            patch("ia_contexto.sugerir_dados_sensiveis", return_value=sugestoes),
        ):
            resposta = cliente.post(
                "/api/analisar",
                files={
                    "arquivo": (
                        "contexto.txt",
                        b"Paciente compareceu ao consultorio.\n",
                        "text/plain",
                    )
                },
            )

        self.assertEqual(resposta.status_code, 200)
        contextuais = [
            item for item in resposta.json()["itens"]
            if item["origem"] == "contexto"
        ]
        self.assertEqual(len(contextuais), 1)
        self.assertEqual(contextuais[0]["dado"], "diagnóstico de diabetes")
        self.assertEqual(contextuais[0]["tipo"], "SAUDE")
        self.assertFalse(contextuais[0]["selecionar_por_padrao"])
        self.assertTrue(contextuais[0]["revisar"])
        self.assertNotIn("compareceu ao consultorio", resposta.text)

    def test_referencia_lgpd_vem_da_base_oficial(self):
        import conhecimento_lgpd

        sugestoes = [
            {
                "trecho": "diagnóstico de diabetes",
                "inicio": 0,
                "fim": 23,
                "categoria": "SAUDE",
                "contexto_presidio": ["diagnóstico"],
                "confianca": 0.93,
            }
        ]
        with (
            patch.object(api, "IA_CONTEXTO", True),
            patch("ia_contexto.sugerir_dados_sensiveis", return_value=sugestoes),
        ):
            resposta = cliente.post(
                "/api/analisar",
                files={
                    "arquivo": (
                        "lgpd.txt",
                        "diagnóstico de diabetes\n".encode("utf-8"),
                        "text/plain",
                    )
                },
            )

        contextual = next(
            item for item in resposta.json()["itens"]
            if item["origem"] == "contexto"
        )
        ids = {ref["id"] for ref in contextual["referencias_lgpd"]}
        self.assertIn("art5-II", ids)
        self.assertIn("art11", ids)
        self.assertTrue(
            all(ref["tipo"] == "literal" for ref in contextual["referencias_lgpd"])
        )
        # Categoria sem redação literal na lei precisa vir marcada como interpretação.
        interpretacoes = conhecimento_lgpd.referencias("PLANEJAMENTO_FAMILIAR")
        self.assertTrue(any(ref["tipo"] == "interpretacao" for ref in interpretacoes))

    def test_offsets_errados_sao_recalculados_pelo_trecho(self):
        texto = "Paciente com diagnóstico de asma."
        sugestoes = [
            ia_contexto.SugestaoContexto(
                trecho="diagnóstico de asma",
                inicio=0,  # errado de propósito, como o Gemini costuma devolver
                fim=5,
                categoria="SAUDE",
                contexto_presidio=["Paciente"],
                confianca=0.9,
            )
        ]
        resultado = ia_contexto._validar(sugestoes, texto)

        self.assertEqual(len(resultado), 1)
        item = resultado[0]
        self.assertEqual(item["inicio"], texto.index("diagnóstico de asma"))
        self.assertEqual(texto[item["inicio"]:item["fim"]], item["trecho"])

    def test_modo_gemini_usa_function_calling(self):
        with patch.object(
            ia_contexto,
            "BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        ):
            self.assertEqual(ia_contexto.modo_instructor(), instructor.Mode.TOOLS)

        with patch.object(ia_contexto, "BASE_URL", "https://openrouter.ai/api/v1"):
            self.assertEqual(ia_contexto.modo_instructor(), instructor.Mode.JSON)

    def test_chave_api_aceita_provedor_alternativo(self):
        with patch.dict(
            os.environ,
            {"IA_API_KEY": "chave-ia", "OPENROUTER_API_KEY": "chave-antiga"},
        ):
            self.assertEqual(ia_contexto.chave_api(), "chave-ia")

        with patch.dict(
            os.environ,
            {"IA_API_KEY": "", "OPENROUTER_API_KEY": "chave-antiga"},
        ):
            self.assertEqual(ia_contexto.chave_api(), "chave-antiga")

    def test_ia_lenta_guarda_resposta_tardia_em_cache(self):
        def consulta_lenta(_texto: str, _api_key: str):
            time.sleep(0.4)
            return [{"trecho": "diagnóstico de diabetes"}]

        texto = "Paciente com diagnóstico de diabetes."
        esperado = [{"trecho": "diagnóstico de diabetes"}]
        ia_contexto._cache.clear()
        with (
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "teste"}),
            patch.object(ia_contexto, "TEMPO_TOTAL", 0.1),
            patch.object(ia_contexto, "_consultar", side_effect=consulta_lenta),
        ):
            inicio = time.perf_counter()
            primeiro = ia_contexto.sugerir_dados_sensiveis(texto)
            decorrido = time.perf_counter() - inicio

            self.assertEqual(primeiro, [])
            self.assertLess(decorrido, 0.3)

            time.sleep(0.5)
            self.assertEqual(ia_contexto.sugerir_dados_sensiveis(texto), esperado)

        ia_contexto._cache.clear()


class TesteMetricaDeLog(unittest.TestCase):
    def test_contagem_nao_e_numero_de_chaves(self):
        evidencias = {
            "emails": [],
            "emails_reparados": [{"valor": "joao@example.com"}],
            "cartoes_credito_validados": [],
            "numeros_de_oficio": [],
            "cpfs_validos": ["123.456.789-09"],
            "cnpjs_validos": [],
            "rgs_rotulados": [],
        }
        self.assertEqual(len(evidencias), 7)
        self.assertEqual(api.contar_evidencias(evidencias), (2, 2))

    def test_log_usa_campos_explicitos(self):
        api._cache.clear()
        conteudo = b"CPF: 123.456.789-09\n"
        with self.assertLogs("privacydocs", level="INFO") as capturado:
            cliente.post(
                "/api/analisar",
                files={"arquivo": ("metrica.txt", conteudo, "text/plain")},
            )
        linhas = [
            linha for linha in capturado.output if "deteccao concluida" in linha
        ]
        self.assertEqual(len(linhas), 1)
        self.assertIn("grupos_regex=", linhas[0])
        self.assertIn("candidatos_regex=", linhas[0])
        # O campo antigo era solto: "70 ms: regex=7 presidio=..."
        self.assertNotRegex(linhas[0], r"(?<![a-z_])regex=\d+")


if __name__ == "__main__":
    unittest.main()
