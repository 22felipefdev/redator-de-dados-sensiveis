import { createElement as h, useState } from 'react';
import type { PointerEvent } from 'react';
import type { Caixa, Dado, PaginaVisivel } from '../../lib/redactor/types';
import { cn } from '../../lib/utils';

interface DocumentViewerProps {
    paginas: PaginaVisivel[];
    dados?: Dado[];
    selecionados?: Set<string>;
    destacado?: string | null;
    modoDesenho?: boolean;
    onAlternar?: (id: string) => void;
    onDesenhar?: (caixa: Caixa) => void;
    rotulo: string;
}

interface PaginaDocumentoProps extends Omit<DocumentViewerProps, 'paginas' | 'rotulo'> {
    pagina: PaginaVisivel;
    indice: number;
    total: number;
}

function PaginaDocumento({
    pagina,
    indice,
    total,
    dados = [],
    selecionados,
    destacado,
    modoDesenho,
    onAlternar,
    onDesenhar,
}: PaginaDocumentoProps) {
    const [inicio, setInicio] = useState<{ x: number; y: number } | null>(null);
    const [atual, setAtual] = useState<{ x: number; y: number } | null>(null);

    const paraPagina = (evento: PointerEvent<HTMLDivElement>) => {
        const retangulo = evento.currentTarget.getBoundingClientRect();
        if (!retangulo.width || !retangulo.height) return { x: 0, y: 0 };
        const x = Math.min(Math.max(evento.clientX - retangulo.left, 0), retangulo.width);
        const y = Math.min(Math.max(evento.clientY - retangulo.top, 0), retangulo.height);
        return {
            x: (x / retangulo.width) * pagina.largura,
            y: (y / retangulo.height) * pagina.altura,
        };
    };

    const finalizar = () => {
        if (inicio && atual && onDesenhar) {
            const largura = Math.abs(atual.x - inicio.x);
            const altura = Math.abs(atual.y - inicio.y);
            if (largura > 6 && altura > 6) {
                onDesenhar({
                    pagina: indice,
                    x: Math.min(inicio.x, atual.x),
                    y: Math.min(inicio.y, atual.y),
                    largura,
                    altura,
                });
            }
        }
        setInicio(null);
        setAtual(null);
    };

    const percentual = (caixa: Omit<Caixa, 'pagina'>) => ({
        left: `${(caixa.x / pagina.largura) * 100}%`,
        top: `${(caixa.y / pagina.altura) * 100}%`,
        width: `${(caixa.largura / pagina.largura) * 100}%`,
        height: `${(caixa.altura / pagina.altura) * 100}%`,
    });

    return h(
        'figure',
        { className: 'flex w-full max-w-3xl flex-col gap-2' },
        h(
            'div',
            {
                className:
                    'relative w-full overflow-hidden rounded-sm bg-card shadow-[0_2px_4px_rgb(3_12_35/0.2),0_16px_40px_-12px_rgb(3_12_35/0.5)]',
                style: { aspectRatio: `${pagina.largura} / ${pagina.altura}` },
            },
            h('img', {
                src: pagina.url,
                alt: `Página ${indice + 1} de ${total}`,
                className: 'absolute inset-0 size-full select-none',
                draggable: false,
            }),
            dados.flatMap((dado) =>
                dado.caixas.map((caixa, posicao) => {
                    if (caixa.pagina !== indice) return null;
                    const marcado = selecionados?.has(dado.id) ?? false;
                    const emFoco = destacado === dado.id;
                    return h('button', {
                        key: `${dado.id}-${posicao}`,
                        id: posicao === 0 ? `caixa-${dado.id}` : undefined,
                        type: 'button',
                        disabled: modoDesenho,
                        'aria-pressed': marcado,
                        'aria-label': `${dado.categoria}: ${dado.valor}. ${marcado ? 'Será censurado' : 'Não será censurado'}`,
                        title: `${dado.categoria} · ${dado.valor}`,
                        onClick: () => onAlternar?.(dado.id),
                        style: percentual(caixa),
                        className: cn(
                            'absolute rounded-[2px] transition-[background-color,box-shadow] outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1',
                            marcado
                                ? 'bg-redaction hover:bg-redaction/85'
                                : 'bg-accent/55 mix-blend-multiply ring-1 ring-redaction/30 hover:bg-accent/80',
                            emFoco && 'ring-[3px] ring-accent',
                            modoDesenho && 'pointer-events-none',
                        ),
                    });
                }),
            ),
            modoDesenho
                ? h(
                      'div',
                      {
                          className: 'absolute inset-0 cursor-crosshair touch-none',
                          onPointerDown: (evento: PointerEvent<HTMLDivElement>) => {
                              evento.currentTarget.setPointerCapture(evento.pointerId);
                              const ponto = paraPagina(evento);
                              setInicio(ponto);
                              setAtual(ponto);
                          },
                          onPointerMove: (evento: PointerEvent<HTMLDivElement>) =>
                              inicio && setAtual(paraPagina(evento)),
                          onPointerUp: finalizar,
                          onPointerCancel: finalizar,
                      },
                      inicio && atual
                          ? h('span', {
                                className: 'absolute border-2 border-dashed border-redaction bg-redaction/60',
                                style: percentual({
                                    x: Math.min(inicio.x, atual.x),
                                    y: Math.min(inicio.y, atual.y),
                                    largura: Math.abs(atual.x - inicio.x),
                                    altura: Math.abs(atual.y - inicio.y),
                                }),
                            })
                          : null,
                  )
                : null,
        ),
        h('figcaption', { className: 'text-center font-mono text-xs text-muted-foreground' }, `${indice + 1} / ${total}`),
    );
}

export function DocumentViewer({
    paginas,
    dados = [],
    selecionados,
    destacado,
    modoDesenho = false,
    onAlternar,
    onDesenhar,
    rotulo,
}: DocumentViewerProps) {
    return h(
        'section',
        { 'aria-label': rotulo, className: 'flex flex-col items-center gap-6 px-4 py-6 md:px-8 md:py-8' },
        paginas.map((pagina, indice) =>
            h(PaginaDocumento, {
                key: pagina.url,
                indice,
                total: paginas.length,
                pagina,
                dados,
                selecionados,
                destacado,
                modoDesenho,
                onAlternar,
                onDesenhar,
            }),
        ),
    );
}
