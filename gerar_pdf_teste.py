# ARQUIVO GERADO POR IA APENAS PARA TESTES
# python gerar_pdf_teste.py PARA EXECUTAR E CRIAR UM PDF COM DADOS FALSOS

import os


def instalar_dependencia():
    try:
        import reportlab
    except ImportError:
        print("A instalar a biblioteca 'reportlab'...")
        os.system("pip install reportlab")


instalar_dependencia()

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def gerar_pdf_teste():
    nome_ficheiro = "documento_teste.pdf"
    c = canvas.Canvas(nome_ficheiro, pagesize=letter)

    # Título do Documento
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "RELATÓRIO DE RECURSOS HUMANOS - CONFIDENCIAL")

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(
        50, 735, "Aviso: Documento de uso interno contendo dados pessoais."
    )

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 700, "1. DADOS DE IDENTIFICAÇÃO DO COLABORADOR")

    c.setFont("Helvetica", 10)
    linhas_texto = [
        "Nome Completo: Carlos Eduardo de Oliveira",
        "CPF: 341.892.508-11 | RG: 44.123.987-X SSP/SP",
        "Data de Nascimento: 12/08/1988",
        "Telefone Pessoal: (11) 97123-4567",
        "E-mail Pessoal: carlos.oliveira.teste@emailfalso.com",
        "Endereço: Rua das Palmeiras, 450, Apto 32 - São Paulo/SP",
        "",
        "2. INFORMAÇÕES FINANCEIRAS E CONTRATUAIS",
        "Cargo: Analista de Sistemas Sénior",
        "Salário Base: R$ 14.850,00",
        "Cartão Corporativo: 4532 8912 3456 7890 (Validade: 11/28 | CVV: 891)",
        "Dados Bancários: Banco do Brasil (001) | Agência: 3412-9 | Conta:"
        " 89123-4",
        "Chave PIX: carlos.oliveira.teste@emailfalso.com",
        "",
        "3. HISTÓRICO MÉDICO E SAÚDE OCUPACIONAL",
        (
            "CID-10: F41.1 (Transtorno de ansiedade generalizada) - Atestado de"
            " 5 dias."
        ),
        (
            "Observação Médica: Colaborador em acompanhamento psicológico"
            " contínuo."
        ),
    ]

    y = 680
    for linha in linhas_texto:
        if (
            linha.startswith("2.")
            or linha.startswith("3.")
            or linha.startswith("1.")
        ):
            c.setFont("Helvetica-Bold", 11)
            y -= 10
        else:
            c.setFont("Helvetica", 10)

        c.drawString(50, y, linha)
        y -= 20

    c.save()
    print(f"Ficheiro '{nome_ficheiro}' criado com sucesso na pasta local!")


if __name__ == "__main__":
    gerar_pdf_teste()