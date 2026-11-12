
"use strict";

const arquivoInput = document.getElementById("arquivo");
const mensagem = document.getElementById("mensagem");
const listaDados = document.getElementById("lista-dados");
const previa = document.getElementById("previa");
const botaoBaixar = document.getElementById("baixar");

pdfjsLib.GlobalWorkerOptions.workerSrc =
"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

let arquivoAtual = null;
let paginas = [];
let dadosEncontrados = [];

const padroes = [
    { categoria: "CPF", regex: /\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g },
    { categoria: "E-mail", regex: /[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}/g },
    { categoria: "Telefone", regex: /(?:\+55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-.\s]?\d{4}\b/g },
    { categoria: "CEP", regex: /\b\d{5}-?\d{3}\b/g },
    { categoria: "RG", regex: /\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]\b/g }
];

// LIMPAR DADOS TEMPORÁRIOS
function limparTela() {
    paginas.forEach(pagina => {
        pagina.canvas.width = 0;
        pagina.canvas.height = 0;
    });

    arquivoAtual = null;
    paginas = [];
    dadosEncontrados = [];

    arquivoInput.value = "";
    listaDados.innerHTML = "";
    previa.textContent = "A pré-visualização aparecerá aqui.";
    botaoBaixar.disabled = true;
}

// IDENTIFICAR DADOS NO PDF
arquivoInput.addEventListener("change", async () => {
    const arquivo = arquivoInput.files[0];

    if (!arquivo) return;

    limparTela();

    if (
        arquivo.type !== "application/pdf" &&
        !arquivo.name.toLowerCase().endsWith(".pdf")
    ) {
        mensagem.textContent = "Selecione um arquivo PDF válido.";
        return;
    }

    arquivoAtual = arquivo;
    mensagem.textContent = "Analisando documento...";
    previa.textContent = "Lendo páginas do PDF...";

    try {
        const bytes = new Uint8Array(await arquivo.arrayBuffer());

        const documento = await pdfjsLib.getDocument({
            data: bytes
        }).promise;

        for (let numero = 1; numero <= documento.numPages; numero++) {
            const pagina = await documento.getPage(numero);
            const escala = 1.5;

            const viewport = pagina.getViewport({
                scale: escala
            });

            const canvas = document.createElement("canvas");
            const contexto = canvas.getContext("2d");

            canvas.width = Math.ceil(viewport.width);
            canvas.height = Math.ceil(viewport.height);

            await pagina.render({
                canvasContext: contexto,
                viewport: viewport
            }).promise;

            const conteudo = await pagina.getTextContent();
            const regioes = [];

            conteudo.items.forEach(item => {
                if (!item.str || !item.str.trim()) return;

                const transformacao = pdfjsLib.Util.transform(
                    viewport.transform,
                    item.transform
                );

                const altura = Math.hypot(
                    transformacao[2],
                    transformacao[3]
                );

                const regiao = {
                    x: transformacao[4],
                    y: transformacao[5] - altura,
                    largura: item.width * escala,
                    altura: altura
                };

                padroes.forEach(padrao => {
                    const regex = new RegExp(
                        padrao.regex.source,
                        "g"
                    );

                    for (const resultado of item.str.matchAll(regex)) {
                        const dado = {
                            id: String(dadosEncontrados.length),
                            categoria: padrao.categoria,
                            valor: resultado[0],
                            pagina: numero,
                            regiao: regiao
                        };

                        dadosEncontrados.push(dado);
                        regioes.push(dado);
                    }
                });
            });

            paginas.push({
                canvas: canvas,
                largura: viewport.width,
                altura: viewport.height,
                escala: escala,
                regioes: regioes
            });
        }

        await documento.destroy();

        exibirDados();

        mensagem.textContent = "Análise concluída!";

        previa.textContent = dadosEncontrados.length
            ? dadosEncontrados.length + " informação(ões) identificada(s)."
            : "Nenhum dado identificado. PDFs digitalizados precisam de OCR.";

    } catch (erro) {
        console.error(erro);

        limparTela();

        mensagem.textContent = "Erro ao analisar o PDF.";
        previa.textContent = "Não foi possível ler o documento.";
    }
});

// MOSTRAR DADOS IDENTIFICADOS
function exibirDados() {
    listaDados.innerHTML = "";

    dadosEncontrados.forEach(dado => {
        const label = document.createElement("label");
        const checkbox = document.createElement("input");

        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.value = dado.id;

        label.appendChild(checkbox);

        label.appendChild(
            document.createTextNode(
                ` ${dado.categoria}: ${dado.valor}`
            )
        );

        listaDados.appendChild(label);
        listaDados.appendChild(
            document.createElement("br")
        );
    });

    botaoBaixar.disabled = dadosEncontrados.length === 0;
}

// GERAR PDF ANONIMIZADO
botaoBaixar.addEventListener("click", async () => {
    if (!arquivoAtual) return;

    const selecionados = Array.from(
        listaDados.querySelectorAll("input:checked")
    ).map(item => item.value);

    if (selecionados.length === 0) {
        mensagem.textContent = "Selecione pelo menos um dado.";
        return;
    }

    botaoBaixar.disabled = true;
    mensagem.textContent = "Anonimizando documento...";

    try {
        const pdfFinal = await PDFLib.PDFDocument.create();

        for (const pagina of paginas) {
            const canvas = document.createElement("canvas");

            canvas.width = pagina.canvas.width;
            canvas.height = pagina.canvas.height;

            const contexto = canvas.getContext("2d");

            contexto.drawImage(pagina.canvas, 0, 0);

            pagina.regioes.forEach(dado => {
                if (!selecionados.includes(dado.id)) return;

                contexto.fillStyle = "#000000";

                contexto.fillRect(
                    dado.regiao.x - 2,
                    dado.regiao.y - 2,
                    dado.regiao.largura + 4,
                    dado.regiao.altura + 4
                );
            });

            const imagem = await pdfFinal.embedPng(
                canvas.toDataURL("image/png")
            );

            const novaPagina = pdfFinal.addPage([
                pagina.largura / pagina.escala,
                pagina.altura / pagina.escala
            ]);

            novaPagina.drawImage(imagem, {
                x: 0,
                y: 0,
                width: pagina.largura / pagina.escala,
                height: pagina.altura / pagina.escala
            });

            canvas.width = 0;
            canvas.height = 0;
        }

        const resultado = await pdfFinal.save();

        const blob = new Blob([resultado], {
            type: "application/pdf"
        });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "documento_anonimizado.pdf";

        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => {
            URL.revokeObjectURL(url);
        }, 3000);

        limparTela();

        mensagem.textContent =
            "PDF gerado! Dados temporários limpos.";

    } catch (erro) {
        console.error(erro);

        mensagem.textContent = "Erro ao gerar o PDF.";
        botaoBaixar.disabled = false;
    }
});
