import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from identificador import identificar_arquivo
from ocr import extrair_texto
from regex_parser import extrair_evidencias

"""Input"""


def selecionar_arquivo():
    caminho = filedialog.askopenfilename(title="Selecione um arquivo")

    if not caminho:
        return

    botao_selecionar.config(state="disabled")
    texto_resultado.config(state="disabled")

    threading.Thread(
        target=processamento, args=(caminho,), daemon=True
    ).start()


def limpar():
    texto_resultado.config(state="normal")
    texto_resultado.delete("1.0", tk.END)
    texto_resultado.config(state="disabled")


def processamento(caminho):
    info_arquivo = identificar_arquivo(caminho)
    atualizar_tela(info_arquivo + "\n[...] Extraindo texto (OCR quando necessário)...\n")

    try:
        texto = extrair_texto(caminho)
    except Exception as erro:
        atualizar_tela(info_arquivo + f"\n\n[ERRO NA EXTRAÇÃO/OCR]\n{erro}")
        restaurar_botoes()
        return

    if not texto or not texto.strip():
        atualizar_tela(
            "\n[AVISO] Não foi possível extrair texto deste formato (ou o arquivo está vazio)."
        )
        restaurar_botoes()
        return
    # A análise com IA é opcional: falhas de dependências ou da API não devem
    # impedir que o OCR extraia o texto do documento.
    try:
        from detector import identificar_dados_sensiveis
    except ModuleNotFoundError as erro:
        atualizar_tela(
            info_arquivo
            + "\n\n[OCR CONCLUÍDO — IA NÃO DISPONÍVEL]\n"
            + f"Falta instalar a dependência '{erro.name}' para análise com OpenRouter.\n"
            + "No terminal do ambiente Python do projeto, execute: "
            + "python -m pip install openai instructor httpx\n"
            + "O texto extraído está abaixo:\n\n"
            + texto
        )
        restaurar_botoes()
        return

    atualizar_tela("\n[IA] Analisando dados sensíveis via OpenRouter...\n")

    try:
        evidencias_regex = extrair_evidencias(texto)
        relatorio = identificar_dados_sensiveis(texto, evidencias_regex)

        resultado_ia = "\n Informacoes sensiveis encontradas \n"

        if not relatorio.itens:
            resultado_ia += "\nNenhum dado sensível foi encontrado no arquivo."
        else:
            for item in relatorio.itens:
                resultado_ia += (
                    f"\nDado sensível: {item.dado}\n"
                    f"Tipo: {item.tipo}\n"
                    f"Risco: {item.risco.upper()}\n"
                )
        atualizar_tela(info_arquivo + "\n" + resultado_ia)

    except Exception as erro:
        atualizar_tela(
            info_arquivo +
            "\n\n[ERRO NA ANÁLISE COM OPENROUTER]\n"
            "Confira se OPENROUTER_API_KEY está configurada, se há conexão com a internet "
            "e se o modelo gratuito está disponível e dentro do limite de uso.\n"
            f"Detalhe técnico: {type(erro).__name__}: {erro}"
        )
    restaurar_botoes()


def atualizar_tela(texto):
    def _atualizar():
        texto_resultado.config(state="normal")
        texto_resultado.delete("1.0", tk.END)
        texto_resultado.insert(tk.END, texto)
        texto_resultado.config(state="disabled")

    janela.after(0, _atualizar)


def restaurar_botoes():
    def _restaurar():
        botao_selecionar.config(state="normal")
        botao_limpar.config(state="normal")

    janela.after(0, _restaurar)


"""INTERFACE (Tkinter)"""

janela = tk.Tk()
janela.title("Scanner de dados sensiveis")
janela.geometry("650x450")
janela.resizable(False, False)

titulo = tk.Label(
    janela,
    text="Scanner de dados sensíveis",
    font=("Arial", 20, "bold")
)
titulo.pack(pady=20)

descricao = tk.Label(
    janela,
    text="Selecione um arquivo para identificar seu tipo e verificar se contém dados sensíveis.",
    font=("Arial", 11)
)
descricao.pack(pady=5)

frame_botoes = tk.Frame(janela)
frame_botoes.pack(pady=15)

botao_selecionar = tk.Button(
    frame_botoes,
    text="Selecionar arquivo",
    command=selecionar_arquivo,
    width=20,
    height=2
)
botao_selecionar.pack(side=tk.LEFT, padx=5)

botao_limpar = tk.Button(
    frame_botoes,
    text="Limpar",
    command=limpar,
    width=15,
    height=2
)
botao_limpar.pack(side=tk.LEFT, padx=5)

texto_resultado = tk.Text(
    janela,
    width=70,
    height=16,
    font=("Consolas", 10),
    state="disabled"
)
texto_resultado.pack(padx=20, pady=10)

janela.mainloop()
