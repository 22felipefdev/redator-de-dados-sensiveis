import { createElement as h, useCallback, useState } from 'react';
import { AppHeader } from './components/redactor/app-header';
import { AnalysisProgress } from './components/redactor/analysis-progress';
import { DocumentViewer } from './components/redactor/document-viewer';
import { FindingsPanel } from './components/redactor/findings-panel';
import { ResultPanel } from './components/redactor/result-panel';
import { UploadZone } from './components/redactor/upload-zone';
import { analisarNaApi } from './lib/redactor/api';
import { detectarComApi, detectarLocalmente, indexarPagina, itensParaTexto } from './lib/redactor/detection';
import {
    TAMANHO_MAXIMO,
    carregarImagem,
    gerarImagemCensurada,
    gerarPdfCensurado,
    liberarPaginas,
    renderizarPdf,
    tipoDoArquivo,
} from './lib/redactor/document';
import type { Caixa, Dado, ModoDeteccao, Pagina, Resultado, TipoArquivo, Trecho } from './lib/redactor/types';

type Etapa = 'envio' | 'analisando' | 'revisao' | 'resultado';

export default function App() {
    const [etapa, setEtapa] = useState<Etapa>('envio');
    const [arquivo, setArquivo] = useState<File | null>(null);
    const [tipo, setTipo] = useState<TipoArquivo>('pdf');
    const [paginas, setPaginas] = useState<Pagina[]>([]);
    const [dados, setDados] = useState<Dado[]>([]);
    const [selecionados, setSelecionados] = useState<Set<string>>(new Set());
    const [modo, setModo] = useState<ModoDeteccao>('api');
    const [progresso, setProgresso] = useState('');
    const [detalhe, setDetalhe] = useState('');
    const [erro, setErro] = useState<string | null>(null);
    const [modoDesenho, setModoDesenho] = useState(false);
    const [destacado, setDestacado] = useState<string | null>(null);
    const [gerando, setGerando] = useState(false);
    const [resultado, setResultado] = useState<Resultado | null>(null);

    const descartarResultado = useCallback(() => {
        setResultado((atual) => {
            if (atual) {
                URL.revokeObjectURL(atual.url);
                atual.paginas.forEach((pagina) => URL.revokeObjectURL(pagina.url));
            }
            return null;
        });
    }, []);

    const reiniciar = useCallback(() => {
        descartarResultado();
        setPaginas((atuais) => {
            liberarPaginas(atuais);
            return [];
        });
        setArquivo(null);
        setDados([]);
        setSelecionados(new Set());
        setModoDesenho(false);
        setDestacado(null);
        setErro(null);
        setEtapa('envio');
    }, [descartarResultado]);

    const analisar = useCallback(
        async (selecionado: File) => {
            reiniciar();
            const tipoDetectado = tipoDoArquivo(selecionado.name);
            if (!tipoDetectado) {
                setErro('Formato não suportado. Envie PDF, imagem (PNG, JPG, WEBP) ou texto (TXT, CSV, JSON, LOG, PY).');
                return;
            }
            if (selecionado.size > TAMANHO_MAXIMO) {
                setErro('O arquivo passa do limite de 20 MB.');
                return;
            }

            setArquivo(selecionado);
            setTipo(tipoDetectado);
            setEtapa('analisando');
            setProgresso('Lendo o documento…');
            setDetalhe('Extraindo o texto e preparando a pré-visualização no navegador.');

            // A requisição começa junto com a renderização local para poupar tempo.
            const respostaApi = analisarNaApi(selecionado, () => {
                setProgresso('Aguardando sugestões contextuais (IA)…');
                setDetalhe(
                    'O modelo pode levar alguns segundos; a página não travou. Após 60 s o servidor segue sem sugestões.',
                );
            }).then(
                (valor) => ({ valor, falha: null as unknown | null }),
                (falha: unknown) => ({ valor: null, falha }),
            );

            let novasPaginas: Pagina[] = [];
            let trechos: Trecho[][] = [];

            try {
                if (tipoDetectado === 'pdf') {
                    const bytes = new Uint8Array(await selecionado.arrayBuffer());
                    const renderizado = await renderizarPdf(bytes);
                    novasPaginas = renderizado.paginas;
                    trechos = renderizado.trechos;
                } else if (tipoDetectado === 'imagem') {
                    novasPaginas = [await carregarImagem(selecionado)];
                    trechos = [[]];
                } else {
                    setProgresso('Enviando texto para o scanner…');
                    setDetalhe('Arquivos de texto são apenas sinalizados: o original volta sem alterações.');
                }

                setProgresso('Procurando dados sensíveis…');
                const { valor: resposta, falha: falhaApi } = await respostaApi;
                if (falhaApi) {
                    liberarPaginas(novasPaginas);
                    throw falhaApi;
                }

                let encontrados: Dado[];
                if (resposta) {
                    if (tipoDetectado === 'imagem' && resposta.posicoes) {
                        // O OCR devolve coordenadas no espaço original da imagem.
                        const fator =
                            novasPaginas[0].largura / (resposta.posicoes.largura || novasPaginas[0].largura);
                        trechos = [
                            resposta.posicoes.palavras.map((palavra) => ({
                                texto: palavra.texto,
                                x: palavra.x * fator,
                                y: palavra.y * fator,
                                largura: palavra.largura * fator,
                                altura: palavra.altura * fator,
                            })),
                        ];
                    }

                    const indices = trechos.map((lista, indice) => indexarPagina(indice, lista));
                    encontrados =
                        tipoDetectado === 'texto'
                            ? itensParaTexto(resposta.itens)
                            : detectarComApi(resposta.itens, indices);
                    setModo('api');
                } else if (tipoDetectado === 'texto') {
                    // Sem API não há texto lido no navegador para detectar padrões.
                    encontrados = [];
                    setModo('local');
                } else {
                    encontrados = detectarLocalmente(
                        trechos.map((lista, indice) => indexarPagina(indice, lista)),
                    );
                    setModo('local');
                }

                setPaginas(novasPaginas);
                setDados(encontrados);
                // Sugestões da IA entram desmarcadas: quem decide é o cliente.
                setSelecionados(
                    new Set(encontrados.filter((dado) => dado.selecionarPorPadrao).map((dado) => dado.id)),
                );
                setEtapa('revisao');
            } catch (falha) {
                console.error(falha);
                liberarPaginas(novasPaginas);
                setArquivo(null);
                setErro(falha instanceof Error ? falha.message : 'Não foi possível ler o documento.');
                setEtapa('envio');
            }
        },
        [reiniciar],
    );

    const alternar = useCallback((id: string) => {
        setSelecionados((atuais) => {
            const proximos = new Set(atuais);
            if (proximos.has(id)) proximos.delete(id);
            else proximos.add(id);
            return proximos;
        });
    }, []);

    const marcarTodos = useCallback(
        (marcar: boolean) => setSelecionados(marcar ? new Set(dados.map((dado) => dado.id)) : new Set()),
        [dados],
    );

    const localizar = useCallback((id: string) => {
        setDestacado(id);
        document.getElementById(`caixa-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        window.setTimeout(() => setDestacado((atual) => (atual === id ? null : atual)), 1800);
    }, []);

    const desenhar = useCallback((caixa: Caixa) => {
        const id = `manual-${crypto.randomUUID()}`;
        setDados((atuais) => [
            ...atuais,
            {
                id,
                categoria: 'Área manual',
                valor: 'Área desenhada',
                caixas: [caixa],
                pagina: caixa.pagina,
                revisar: false,
                origem: 'manual',
                selecionarPorPadrao: true,
                referenciasLgpd: [],
            },
        ]);
        setSelecionados((atuais) => new Set(atuais).add(id));
    }, []);

    const remover = useCallback((id: string) => {
        setDados((atuais) => atuais.filter((dado) => dado.id !== id));
        setSelecionados((atuais) => {
            const proximos = new Set(atuais);
            proximos.delete(id);
            return proximos;
        });
    }, []);

    const gerar = useCallback(async () => {
        if (!arquivo) return;
        const escolhidos = dados.filter((dado) => selecionados.has(dado.id));
        const caixas = escolhidos.flatMap((dado) => dado.caixas);
        // Texto não recebe tarja: a contagem e as referências cobrem todos os
        // itens sinalizados, inclusive as sugestões desmarcadas da IA.
        const considerados = tipo === 'texto' ? dados : escolhidos;
        if (tipo !== 'texto' && !caixas.length) return;

        setGerando(true);
        setErro(null);
        setModoDesenho(false);
        descartarResultado();

        try {
            const base = arquivo.name.replace(/\.[^.]+$/, '');
            let blob: Blob;
            let nome: string;
            let previa: Resultado['paginas'];
            const referencias = [
                ...new Set(
                    considerados.flatMap((dado) =>
                        dado.referenciasLgpd.map((referencia) =>
                            referencia.tipo
                                ? `${referencia.titulo} (${referencia.tipo})`
                                : referencia.titulo,
                        ),
                    ),
                ),
            ];

            if (tipo === 'texto') {
                // Ainda não há regra de censura para texto: devolve o original.
                blob = arquivo;
                nome = arquivo.name;
                previa = [];
            } else if (tipo === 'pdf') {
                const bytes = await gerarPdfCensurado(paginas, caixas);
                blob = new Blob([new Uint8Array(bytes)], { type: 'application/pdf' });
                nome = `${base}_censurado.pdf`;
                const { paginas: renderizadas } = await renderizarPdf(bytes, 1.5);
                previa = renderizadas.map(({ url, largura, altura, canvas }) => {
                    canvas.width = 0;
                    canvas.height = 0;
                    return { url, largura, altura };
                });
            } else {
                const imagem = await gerarImagemCensurada(paginas[0], caixas, arquivo.name);
                blob = imagem.blob;
                nome = `${base}_censurado.${imagem.extensao}`;
                previa = [
                    {
                        url: URL.createObjectURL(blob),
                        largura: paginas[0].largura,
                        altura: paginas[0].altura,
                    },
                ];
            }

            setResultado({
                url: URL.createObjectURL(blob),
                nome,
                tamanho: blob.size,
                areas: tipo === 'texto' ? dados.length : caixas.length,
                paginas: previa,
                referencias,
                texto: tipo === 'texto',
            });
            setEtapa('resultado');
        } catch (falha) {
            console.error(falha);
            setErro('Não foi possível gerar o arquivo censurado. Tente novamente.');
        } finally {
            setGerando(false);
        }
    }, [arquivo, dados, selecionados, tipo, paginas, descartarResultado]);

    const voltarParaRevisao = useCallback(() => {
        descartarResultado();
        setEtapa('revisao');
    }, [descartarResultado]);

    const etapaAtual = etapa === 'resultado' ? 2 : etapa === 'revisao' ? 1 : 0;

    return h(
        'div',
        { className: 'flex min-h-dvh flex-col lg:h-dvh' },
        h(AppHeader, { etapaAtual }),
        etapa === 'envio' ? h(UploadZone, { onArquivo: analisar, erro }) : null,
        etapa === 'analisando' && arquivo
            ? h(AnalysisProgress, { nomeArquivo: arquivo.name, mensagem: progresso, detalhe })
            : null,
        etapa === 'revisao' && arquivo
            ? h(
                  'main',
                  { className: 'flex flex-1 flex-col lg:grid lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_400px]' },
                  h(
                      'div',
                      { className: 'flex flex-col lg:min-h-0 lg:overflow-y-auto' },
                      modoDesenho
                          ? h(
                                'p',
                                {
                                    role: 'status',
                                    className:
                                        'sticky top-0 z-10 border-b border-border bg-accent px-4 py-2 text-center text-sm font-medium text-accent-foreground',
                                },
                                'Arraste sobre a página para cobrir uma área.',
                            )
                          : null,
                      tipo === 'texto'
                          ? h(
                                'section',
                                {
                                    className:
                                        'flex flex-1 flex-col items-center justify-center gap-3 px-6 py-16 text-center',
                                },
                                h('h2', { className: 'text-lg font-semibold' }, 'Arquivo de texto'),
                                h(
                                    'p',
                                    { className: 'max-w-md text-sm leading-relaxed text-muted-foreground' },
                                    'O conteúdo é enviado só para a API detectar dados. Não há pré-visualização visual e o original será devolvido sem alterações.',
                                ),
                            )
                          : h(DocumentViewer, {
                                rotulo: 'Documento original com dados destacados',
                                paginas: paginas.map((pagina) => ({
                                    url: pagina.url,
                                    largura: pagina.largura,
                                    altura: pagina.altura,
                                })),
                                dados,
                                selecionados,
                                destacado,
                                modoDesenho,
                                onAlternar: alternar,
                                onDesenhar: desenhar,
                            }),
                  ),
                  h(FindingsPanel, {
                      nomeArquivo: arquivo.name,
                      tipo,
                      modo,
                      dados,
                      selecionados,
                      modoDesenho,
                      gerando,
                      erro,
                      onAlternar: alternar,
                      onTodos: marcarTodos,
                      onLocalizar: localizar,
                      onRemover: remover,
                      onModoDesenho: setModoDesenho,
                      onGerar: () => void gerar(),
                      onCancelar: reiniciar,
                  }),
              )
            : null,
        etapa === 'resultado' && resultado
            ? h(
                  'main',
                  { className: 'flex flex-1 flex-col lg:grid lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_400px]' },
                  h(
                      'div',
                      { className: 'lg:min-h-0 lg:overflow-y-auto' },
                      resultado.paginas.length > 0
                          ? h(DocumentViewer, {
                                rotulo: 'Pré-visualização do documento censurado',
                                paginas: resultado.paginas,
                            })
                          : h(
                                'section',
                                {
                                    className:
                                        'flex flex-1 flex-col items-center justify-center gap-3 px-6 py-16 text-center',
                                },
                                h('h2', { className: 'text-lg font-semibold' }, 'Texto sinalizado'),
                                h(
                                    'p',
                                    { className: 'max-w-md text-sm leading-relaxed text-muted-foreground' },
                                    'O arquivo original está pronto para download. Nenhum caractere foi alterado.',
                                ),
                            ),
                  ),
                  h(ResultPanel, {
                      resultado,
                      referencias: resultado.referencias,
                      onVoltar: voltarParaRevisao,
                      onNovo: reiniciar,
                  }),
              )
            : null,
    );
}
