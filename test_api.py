"""Testes da API. Execute: docker compose exec api python -m unittest -v test_api"""
import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

import api
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


if __name__ == "__main__":
    unittest.main()
