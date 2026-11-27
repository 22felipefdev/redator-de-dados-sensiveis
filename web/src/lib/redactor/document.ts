import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import type { Caixa, Pagina, Trecho, TipoArquivo } from './types';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

const EXTENSOES_IMAGEM = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'];
const EXTENSOES_TEXTO = ['.txt', '.csv', '.json', '.log', '.py'];

export const ACEITOS = [...EXTENSOES_TEXTO, '.pdf', ...EXTENSOES_IMAGEM].join(',');
export const TAMANHO_MAXIMO = 20 * 1024 * 1024;

export function tipoDoArquivo(nome: string): TipoArquivo | null {
    const ponto = nome.lastIndexOf('.');
    const extensao = ponto < 0 ? '' : nome.slice(ponto).toLowerCase();
    if (extensao === '.pdf') return 'pdf';
    if (EXTENSOES_IMAGEM.includes(extensao)) return 'imagem';
    if (EXTENSOES_TEXTO.includes(extensao)) return 'texto';
    return null;
}

function extensaoImagem(nome: string): string {
    const extensao = nome.slice(nome.lastIndexOf('.') + 1).toLowerCase();
    if (extensao === 'webp' || extensao === 'png') return extensao;
    if (extensao === 'jpg' || extensao === 'jpeg') return 'jpg';
    // O navegador não exporta TIFF/BMP: usa PNG.
    return 'png';
}

function novoCanvas(largura: number, altura: number) {
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(largura);
    canvas.height = Math.ceil(altura);
    const contexto = canvas.getContext('2d');
    if (!contexto) throw new Error('Seu navegador não suporta Canvas 2D.');
    return { canvas, contexto };
}

function canvasParaBlob(canvas: HTMLCanvasElement, tipo = 'image/png', qualidade?: number) {
    return new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
            (blob) => (blob ? resolve(blob) : reject(new Error('Falha ao exportar a página.'))),
            tipo,
            qualidade,
        );
    });
}

async function paginaDoCanvas(canvas: HTMLCanvasElement, escala: number): Promise<Pagina> {
    const blob = await canvasParaBlob(canvas);
    return {
        canvas,
        url: URL.createObjectURL(blob),
        largura: canvas.width,
        altura: canvas.height,
        escala,
    };
}

export async function renderizarPdf(
    bytes: Uint8Array,
    escala = 2,
): Promise<{ paginas: Pagina[]; trechos: Trecho[][] }> {
    // O pdf.js transfere o buffer para o worker; a cópia preserva o original.
    const carregamento = pdfjsLib.getDocument({ data: bytes.slice() });
    const documento = await carregamento.promise;
    const paginas: Pagina[] = [];
    const trechos: Trecho[][] = [];

    try {
        for (let numero = 1; numero <= documento.numPages; numero++) {
            const pagina = await documento.getPage(numero);
            const viewport = pagina.getViewport({ scale: escala });
            const { canvas, contexto } = novoCanvas(viewport.width, viewport.height);
            await pagina.render({ canvas, canvasContext: contexto, viewport }).promise;

            const conteudo = await pagina.getTextContent();
            const daPagina: Trecho[] = [];
            for (const item of conteudo.items) {
                if (!('str' in item) || !item.str.trim()) continue;
                const t = pdfjsLib.Util.transform(viewport.transform, item.transform);
                const altura = Math.hypot(t[2], t[3]);
                daPagina.push({
                    texto: item.str,
                    x: t[4],
                    y: t[5] - altura,
                    largura: (item.width ?? 0) * escala,
                    altura,
                });
            }

            trechos.push(daPagina);
            paginas.push(await paginaDoCanvas(canvas, escala));
            pagina.cleanup();
        }
    } finally {
        await carregamento.destroy();
    }

    return { paginas, trechos };
}

export async function carregarImagem(arquivo: File): Promise<Pagina> {
    const bitmap = await createImageBitmap(arquivo);
    const { canvas, contexto } = novoCanvas(bitmap.width, bitmap.height);
    contexto.drawImage(bitmap, 0, 0);
    bitmap.close();
    return paginaDoCanvas(canvas, 1);
}

function aplicarTarjas(pagina: Pagina, indice: number, caixas: Caixa[]) {
    const { canvas, contexto } = novoCanvas(pagina.canvas.width, pagina.canvas.height);
    contexto.drawImage(pagina.canvas, 0, 0);
    contexto.fillStyle = '#000000';
    for (const caixa of caixas) {
        if (caixa.pagina !== indice) continue;
        contexto.fillRect(caixa.x, caixa.y, caixa.largura, caixa.altura);
    }
    return canvas;
}

// Cada página vira imagem com a tarja "queimada": o texto coberto não fica
// escondido por baixo, então não dá para copiá-lo nem recuperá-lo.
export async function gerarPdfCensurado(paginas: Pagina[], caixas: Caixa[]): Promise<Uint8Array> {
    const { PDFDocument } = await import('pdf-lib');
    const pdf = await PDFDocument.create();

    for (const [indice, pagina] of paginas.entries()) {
        const canvas = aplicarTarjas(pagina, indice, caixas);
        const png = await canvasParaBlob(canvas);
        const imagem = await pdf.embedPng(await png.arrayBuffer());
        const largura = pagina.largura / pagina.escala;
        const altura = pagina.altura / pagina.escala;
        pdf.addPage([largura, altura]).drawImage(imagem, { x: 0, y: 0, width: largura, height: altura });
        canvas.width = 0;
        canvas.height = 0;
    }

    return pdf.save();
}

export async function gerarImagemCensurada(pagina: Pagina, caixas: Caixa[], nomeOriginal: string) {
    const canvas = aplicarTarjas(pagina, 0, caixas);
    const extensao = extensaoImagem(nomeOriginal);
    const mime = extensao === 'jpg' ? 'image/jpeg' : `image/${extensao}`;
    const blob = await canvasParaBlob(canvas, mime, 0.92);
    canvas.width = 0;
    canvas.height = 0;
    return { blob, extensao };
}

export function liberarPaginas(paginas: { url: string; canvas?: HTMLCanvasElement }[]) {
    for (const pagina of paginas) {
        URL.revokeObjectURL(pagina.url);
        if (pagina.canvas) {
            pagina.canvas.width = 0;
            pagina.canvas.height = 0;
        }
    }
}
