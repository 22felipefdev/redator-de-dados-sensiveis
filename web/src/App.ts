import {
    Fragment,
    createElement,
    useCallback,
    useState,
} from 'react';
import type { ChangeEvent } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.js?url';
import { PDFDocument } from 'pdf-lib';
import './App.css';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

const EXTENSOES_PDF = ['.pdf'];
const EXTENSOES_IMAGEM = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp'];
const EXTENSOES_TEXTO = ['.txt', '.csv', '.json', '.log', '.py'];
const ACEITAS = [...EXTENSOES_PDF, ...EXTENSOES_IMAGEM, ...EXTENSOES_TEXTO];

type TipoArquivo = 'pdf' | 'imagem' | 'texto';

function tipoArquivo(nome: string): TipoArquivo | null {
    const ponto = nome.lastIndexOf('.');
    const extensao = ponto < 0 ? '' : nome.slice(ponto).toLowerCase();
    if (EXTENSOES_PDF.includes(extensao)) {
        return 'pdf';
    }
    if (EXTENSOES_IMAGEM.includes(extensao)) {
        return 'imagem';
    }
    if (EXTENSOES_TEXTO.includes(extensao)) {
        return 'texto';
    }
    return null;
}

function extensaoArquivo(nome: string): string {
    const ponto = nome.lastIndexOf('.');
    return ponto < 0 ? '' : nome.slice(ponto).toLowerCase();
}

interface Regiao {
    id: string;
    x: number;
    y: number;
    largura: number;
    altura: number;
}

interface Trecho {
    texto: string;
    pagina: number;
    x: number;
    y: number;
    largura: number;
    altura: number;
}

interface Palavra {
    texto: string;
    x: number;
    y: number;
    largura: number;
    altura: number;
}

interface Posicoes {
    largura: number;
    altura: number;
    palavras: Palavra[];
}

interface Pagina {
    canvas: HTMLCanvasElement;
    largura: number;
    altura: number;
    escala: number;
    regioes: Regiao[];
}

interface ItemApi {
    dado: string;
    tipo: string;
    risco: string;
    revisar: boolean;
    original: string | null;
}

interface RespostaApi {
    arquivo: string;
    posicoes: Posicoes | null;
    itens: ItemApi[];
}

interface Dado {
    id: string;
    categoria: string;
    valor: string;
    pagina: number;
    revisar: boolean;
}

// Comparação tolerante a pontuação, espaços e acentos: o backend devolve o
// valor normalizado, enquanto o OCR lê o texto como ele está no documento.
function normalizar(texto: string): string {
    return texto
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '');
}

function candidatos(item: ItemApi): string[] {
    return [item.original, item.dado].filter(
        (valor): valor is string => Boolean(valor),
    );
}

function localizar(item: ItemApi, trechos: Trecho[]): Trecho | undefined {
    for (const candidato of candidatos(item)) {
        const alvo = normalizar(candidato);
        if (alvo.length < 4) {
            continue;
        }
        const encontrado = trechos.find((trecho) =>
            normalizar(trecho.texto).includes(alvo),
        );
        if (encontrado) {
            return encontrado;
        }
    }
    return undefined;
}

// O OCR devolve palavras em ordem de leitura. Um dado pode virar duas ou mais
// palavras (ex.: "123.456.789-09"), então procuramos janelas consecutivas e
// devolvemos a caixa que envolve todas elas.
function caixaEmPalavras(
    item: ItemApi,
    palavras: Palavra[],
): Omit<Regiao, 'id'> | undefined {
    const normalizadas = palavras.map((palavra) => normalizar(palavra.texto));

    for (const candidato of candidatos(item)) {
        const alvo = normalizar(candidato);
        if (alvo.length < 4) {
            continue;
        }

        for (let inicio = 0; inicio < palavras.length; inicio++) {
            let acumulado = '';
            for (
                let fim = inicio;
                fim < Math.min(inicio + 10, palavras.length);
                fim++
            ) {
                acumulado += normalizadas[fim];
                // Sem o limite de tamanho, uma janela que começa no topo da
                // página acabaria casando o fim e cobrindo o documento inteiro.
                if (
                    !acumulado.includes(alvo) ||
                    acumulado.length - alvo.length > Math.max(8, alvo.length)
                ) {
                    continue;
                }

                const encontradas = palavras.slice(inicio, fim + 1);
                const x = Math.min(...encontradas.map((palavra) => palavra.x));
                const y = Math.min(...encontradas.map((palavra) => palavra.y));
                const direita = Math.max(
                    ...encontradas.map((palavra) => palavra.x + palavra.largura),
                );
                const baixo = Math.max(
                    ...encontradas.map((palavra) => palavra.y + palavra.altura),
                );

                return {
                    x: x - 2,
                    y: y - 2,
                    largura: direita - x + 4,
                    altura: baixo - y + 4,
                };
            }
        }
    }

    return undefined;
}

function Sidebar() {
    return createElement(
        'aside',
        { className: 'sidebar' },
        createElement('h2', null, '🔒 PrivacyDocs'),
        createElement(
            'nav',
            null,
            createElement('a', { href: '#' }, 'Início'),
            createElement('a', { href: '#' }, 'Novo documento'),
        ),
        createElement('p', null, 'Sua privacidade é nossa prioridade.'),
    );
}

export default function App() {
    const [arquivo, setArquivo] = useState<File | null>(null);
    const [tipo, setTipo] = useState<TipoArquivo | null>(null);
    const [mensagem, setMensagem] = useState('Selecione um arquivo.');
    const [dados, setDados] = useState<Dado[]>([]);
    const [selecionados, setSelecionados] = useState<string[]>([]);
    const [previa, setPrevia] = useState('A pré-visualização aparecerá aqui.');
    const [processando, setProcessando] = useState(false);
    // Trocar a key remonta o <input> e limpa o arquivo escolhido anteriormente.
    const [chaveInput, setChaveInput] = useState(0);
    const [paginas, setPaginas] = useState<Pagina[]>([]);

    const limparTela = useCallback(() => {
        paginas.forEach((pagina) => {
            pagina.canvas.width = 0;
            pagina.canvas.height = 0;
        });
        setPaginas([]);
        setArquivo(null);
        setTipo(null);
        setDados([]);
        setSelecionados([]);
        setPrevia('A pré-visualização aparecerá aqui.');
        setChaveInput((atual) => atual + 1);
    }, [paginas]);

    const alternar = useCallback((id: string, marcado: boolean) => {
        setSelecionados((atuais) =>
            marcado
                ? [...atuais, id]
                : atuais.filter((item) => item !== id),
        );
    }, []);

    const analisar = useCallback(
        async (selecionado: File) => {
            limparTela();

            const tipoDetectado = tipoArquivo(selecionado.name);
            if (!tipoDetectado) {
                setMensagem(
                    'Formato não suportado. Use PDF, imagem ou arquivo de texto.',
                );
                return;
            }

            setArquivo(selecionado);
            setTipo(tipoDetectado);
            setMensagem('Enviando para o scanner (OCR + Presidio)...');
            setPrevia('Aguardando a API Python...');

            const controlador = new AbortController();
            const temporizador = window.setTimeout(() => controlador.abort(), 90_000);

            try {
                const formulario = new FormData();
                formulario.append('arquivo', selecionado);

                const resposta = await fetch('/api/analisar', {
                    method: 'POST',
                    body: formulario,
                    signal: controlador.signal,
                });

                if (!resposta.ok) {
                    const detalhe = await resposta.text();
                    throw new Error(
                        `API respondeu ${resposta.status}: ${detalhe.slice(0, 200)}`,
                    );
                }

                const resultado = (await resposta.json()) as RespostaApi;
                setMensagem('Scanner concluiu. Preparando o arquivo...');

                const encontrados: Dado[] = [];
                const paginasNovas: Pagina[] = [];
                let semPosicao = 0;

                if (tipoDetectado === 'pdf') {
                    const bytes = new Uint8Array(await selecionado.arrayBuffer());
                    const documento = await pdfjsLib.getDocument({ data: bytes }).promise;
                    const trechos: Trecho[] = [];

                    for (let numero = 1; numero <= documento.numPages; numero++) {
                        const pagina = await documento.getPage(numero);
                        const escala = 1.5;
                        const viewport = pagina.getViewport({ scale: escala });

                        const canvas = document.createElement('canvas');
                        const contexto = canvas.getContext('2d');
                        if (!contexto) {
                            throw new Error('Canvas 2D indisponível.');
                        }
                        canvas.width = Math.ceil(viewport.width);
                        canvas.height = Math.ceil(viewport.height);

                        await pagina.render({ canvasContext: contexto, viewport }).promise;

                        const conteudo = await pagina.getTextContent();

                        for (const item of conteudo.items) {
                            if (!('str' in item) || !item.str || !item.str.trim()) {
                                continue;
                            }

                            const transformacao = pdfjsLib.Util.transform(
                                viewport.transform,
                                item.transform,
                            );
                            const altura = Math.hypot(transformacao[2], transformacao[3]);
                            trechos.push({
                                texto: item.str,
                                pagina: numero,
                                x: transformacao[4],
                                y: transformacao[5] - altura,
                                largura: (item.width ?? 0) * escala,
                                altura,
                            });
                        }

                        paginasNovas.push({
                            canvas,
                            largura: viewport.width,
                            altura: viewport.height,
                            escala,
                            regioes: [],
                        });
                    }

                    await documento.destroy();

                    resultado.itens.forEach((item, indice) => {
                        const id = String(indice);
                        const trecho = localizar(item, trechos);
                        if (trecho) {
                            paginasNovas[trecho.pagina - 1].regioes.push({
                                id,
                                x: trecho.x - 2,
                                y: trecho.y - 2,
                                largura: trecho.largura + 4,
                                altura: trecho.altura + 4,
                            });
                        } else {
                            semPosicao += 1;
                        }
                        encontrados.push({
                            id,
                            categoria: item.tipo,
                            valor: item.dado,
                            pagina: trecho?.pagina ?? 0,
                            revisar: item.revisar || !trecho,
                        });
                    });
                } else if (tipoDetectado === 'imagem') {
                    const bitmap = await createImageBitmap(selecionado);
                    const canvas = document.createElement('canvas');
                    canvas.width = bitmap.width;
                    canvas.height = bitmap.height;
                    const contexto = canvas.getContext('2d');
                    if (!contexto) {
                        bitmap.close();
                        throw new Error('Canvas 2D indisponível.');
                    }
                    contexto.drawImage(bitmap, 0, 0);
                    bitmap.close();

                    paginasNovas.push({
                        canvas,
                        largura: canvas.width,
                        altura: canvas.height,
                        escala: 1,
                        regioes: [],
                    });

                    const palavras = resultado.posicoes?.palavras ?? [];
                    resultado.itens.forEach((item, indice) => {
                        const id = String(indice);
                        const caixa = caixaEmPalavras(item, palavras);
                        if (caixa) {
                            paginasNovas[0].regioes.push({ id, ...caixa });
                        } else {
                            semPosicao += 1;
                        }
                        encontrados.push({
                            id,
                            categoria: item.tipo,
                            valor: item.dado,
                            pagina: caixa ? 1 : 0,
                            revisar: item.revisar || !caixa,
                        });
                    });
                } else {
                    // Arquivo de texto: apenas sinalização. O conteúdo não é alterado.
                    resultado.itens.forEach((item, indice) => {
                        encontrados.push({
                            id: String(indice),
                            categoria: item.tipo,
                            valor: item.dado,
                            pagina: 0,
                            revisar: item.revisar,
                        });
                    });
                }

                setPaginas(paginasNovas);
                setDados(encontrados);
                setSelecionados(encontrados.map((dado) => dado.id));
                setMensagem('Análise concluída!');

                const resumo = [
                    `${encontrados.length} dado(s) sensível(is) sinalizado(s).`,
                ];
                if (tipoDetectado === 'texto') {
                    resumo.push(
                        'O arquivo será devolvido sem alterações; a censura será definida depois.',
                    );
                } else if (semPosicao) {
                    resumo.push(
                        `${semPosicao} sem posição automática: confira manualmente.`,
                    );
                }
                if (!encontrados.length) {
                    resumo.push('Nenhum dado sensível confirmado.');
                }
                setPrevia(resumo.join(' '));
            } catch (erro) {
                console.error(erro);
                const expirou =
                    erro instanceof DOMException && erro.name === 'AbortError';
                limparTela();
                if (expirou) {
                    setMensagem('Tempo esgotado ao analisar.');
                    setPrevia('O servidor demorou mais que o esperado. Tente novamente.');
                    return;
                }
                setMensagem('Erro ao analisar o documento.');
                setPrevia(
                    erro instanceof Error ? erro.message : 'Não foi possível ler o documento.',
                );
            } finally {
                window.clearTimeout(temporizador);
            }
        },
        [limparTela],
    );

    const aoSelecionar = useCallback(
        (evento: ChangeEvent<HTMLInputElement>) => {
            const selecionado = evento.target.files?.[0];
            if (selecionado) {
                void analisar(selecionado);
            }
        },
        [analisar],
    );

    const gerarArquivo = useCallback(async () => {
        if (!arquivo || !tipo) {
            return;
        }
        if (selecionados.length === 0) {
            setMensagem('Selecione pelo menos um dado.');
            return;
        }

        setProcessando(true);
        setMensagem('Preparando o arquivo...');

        try {
            const base = arquivo.name.replace(/\.[^.]+$/, '');
            let blob: Blob;
            let nome: string;

            if (tipo === 'texto') {
                // Ainda não há regra de censura para texto: devolve o original.
                blob = arquivo;
                nome = arquivo.name;
            } else if (tipo === 'imagem') {
                const pagina = paginas[0];
                if (!pagina) {
                    throw new Error('Imagem não disponível.');
                }

                const canvas = document.createElement('canvas');
                canvas.width = pagina.canvas.width;
                canvas.height = pagina.canvas.height;
                const contexto = canvas.getContext('2d');
                if (!contexto) {
                    throw new Error('Canvas 2D indisponível.');
                }
                contexto.drawImage(pagina.canvas, 0, 0);

                pagina.regioes.forEach((regiao) => {
                    if (!selecionados.includes(regiao.id)) {
                        return;
                    }
                    contexto.fillStyle = '#000000';
                    contexto.fillRect(
                        regiao.x,
                        regiao.y,
                        regiao.largura,
                        regiao.altura,
                    );
                });

                const extensao = extensaoArquivo(arquivo.name);
                let mime = 'image/jpeg';
                let ext = extensao;
                if (extensao === '.png') {
                    mime = 'image/png';
                } else if (extensao === '.webp') {
                    mime = 'image/webp';
                } else if (['.tif', '.tiff', '.bmp'].includes(extensao)) {
                    // O navegador não exporta esses formatos: usa PNG.
                    mime = 'image/png';
                    ext = '.png';
                }

                blob = await new Promise<Blob>((resolve, reject) => {
                    canvas.toBlob(
                        (resultado) =>
                            resultado
                                ? resolve(resultado)
                                : reject(new Error('Falha ao exportar a imagem.')),
                        mime,
                        0.92,
                    );
                });
                nome = `${base}_anonimizado${ext}`;

                canvas.width = 0;
                canvas.height = 0;
            } else {
                const pdfFinal = await PDFDocument.create();

                for (const pagina of paginas) {
                    const canvas = document.createElement('canvas');
                    canvas.width = pagina.canvas.width;
                    canvas.height = pagina.canvas.height;
                    const contexto = canvas.getContext('2d');
                    if (!contexto) {
                        throw new Error('Canvas 2D indisponível.');
                    }
                    contexto.drawImage(pagina.canvas, 0, 0);

                    pagina.regioes.forEach((regiao) => {
                        if (!selecionados.includes(regiao.id)) {
                            return;
                        }
                        contexto.fillStyle = '#000000';
                        contexto.fillRect(
                            regiao.x,
                            regiao.y,
                            regiao.largura,
                            regiao.altura,
                        );
                    });

                    const imagem = await pdfFinal.embedPng(canvas.toDataURL('image/png'));
                    const novaPagina = pdfFinal.addPage([
                        pagina.largura / pagina.escala,
                        pagina.altura / pagina.escala,
                    ]);
                    novaPagina.drawImage(imagem, {
                        x: 0,
                        y: 0,
                        width: pagina.largura / pagina.escala,
                        height: pagina.altura / pagina.escala,
                    });

                    canvas.width = 0;
                    canvas.height = 0;
                }

                const resultado = await pdfFinal.save();
                blob = new Blob([new Uint8Array(resultado)], {
                    type: 'application/pdf',
                });
                nome = `${base}_anonimizado.pdf`;
            }

            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = nome;
            document.body.appendChild(link);
            link.click();
            link.remove();

            setTimeout(() => URL.revokeObjectURL(url), 3000);
            limparTela();
            setMensagem(`${nome} gerado! Dados temporários limpos.`);
        } catch (erro) {
            console.error(erro);
            setMensagem('Erro ao gerar o arquivo.');
        } finally {
            setProcessando(false);
        }
    }, [arquivo, tipo, selecionados, limparTela, paginas]);

    const itens = dados.map((dado) =>
        createElement(
            'label',
            { key: dado.id, className: 'dado-item' },
            createElement('input', {
                type: 'checkbox',
                checked: selecionados.includes(dado.id),
                value: dado.id,
                onChange: (evento: ChangeEvent<HTMLInputElement>) =>
                    alternar(dado.id, evento.target.checked),
            }),
            createElement('span', { className: 'dado-tipo' }, dado.categoria),
            createElement('span', { className: 'dado-valor' }, dado.valor),
            dado.revisar
                ? createElement('span', { className: 'dado-revisar' }, 'revisar')
                : null,
        ),
    );

    return createElement(
        Fragment,
        null,
        createElement(Sidebar),
        createElement(
            'main',
            null,
            createElement(
                'header',
                null,
                createElement('h1', null, 'Anonimização de Documentos'),
                createElement(
                    'p',
                    null,
                    'Envie PDF, imagem ou texto, revise os dados e baixe no formato original.',
                ),
            ),
            createElement(
                'section',
                { className: 'upload' },
                createElement('h2', null, 'Enviar arquivo'),
                createElement(
                    'div',
                    { className: 'arquivo-caixa' },
                    createElement('input', {
                        type: 'file',
                        id: 'arquivo',
                        key: chaveInput,
                        className: 'arquivo-input',
                        accept: ACEITAS.join(','),
                        onChange: aoSelecionar,
                    }),
                    createElement(
                        'label',
                        { htmlFor: 'arquivo', className: 'arquivo-dropzone' },
                        createElement(
                            'svg',
                            {
                                className: 'arquivo-icone',
                                viewBox: '0 0 24 24',
                                fill: 'none',
                                stroke: 'currentColor',
                                strokeWidth: 1.8,
                                strokeLinecap: 'round',
                                strokeLinejoin: 'round',
                                'aria-hidden': 'true',
                            },
                            createElement('path', { d: 'M12 16V4m0 0L8 8m4-4 4 4' }),
                            createElement('path', {
                                d: 'M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3',
                            }),
                        ),
                        createElement(
                            'span',
                            { className: 'arquivo-titulo' },
                            arquivo ? arquivo.name : 'Escolher arquivo',
                        ),
                        createElement(
                            'span',
                            { className: 'arquivo-dica' },
                            'PDF, imagem ou texto — clique para selecionar',
                        ),
                    ),
                ),
                createElement('p', { id: 'mensagem' }, mensagem),
            ),
            createElement(
                'section',
                { className: 'dados' },
                createElement('h2', null, 'Dados identificados'),
                createElement(
                    'p',
                    null,
                    'Selecione as informações que deseja anonimizar.',
                ),
                createElement('div', { id: 'lista-dados' }, ...itens),
            ),
            createElement(
                'section',
                { className: 'preview' },
                createElement('h2', null, 'Visualização do resultado'),
                createElement('div', { id: 'previa' }, previa),
            ),
            createElement(
                'section',
                { className: 'download' },
                createElement('h2', null, 'Baixar arquivo'),
                createElement(
                    'p',
                    null,
                    'O arquivo volta no formato original. Textos são apenas sinalizados.',
                ),
                createElement(
                    'button',
                    {
                        id: 'baixar',
                        disabled: processando || dados.length === 0,
                        onClick: () => void gerarArquivo(),
                    },
                    'Baixar no formato original',
                ),
            ),
        ),
    );
}
