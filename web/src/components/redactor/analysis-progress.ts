import { createElement as h } from 'react';
import { cn } from '../../lib/utils';

const LINHAS = ['w-11/12', 'w-4/5', 'w-full', 'w-2/3', 'w-5/6', 'w-3/4', 'w-full', 'w-1/2'];

interface AnalysisProgressProps {
    nomeArquivo: string;
    mensagem: string;
    detalhe: string;
}

export function AnalysisProgress({ nomeArquivo, mensagem, detalhe }: AnalysisProgressProps) {
    return h(
        'main',
        { className: 'flex flex-1 items-center justify-center px-4 py-16' },
        h(
            'div',
            { className: 'flex w-full max-w-sm flex-col items-center gap-8' },
            h(
                'div',
                {
                    'aria-hidden': 'true',
                    className:
                        'relative flex aspect-[1/1.3] w-48 flex-col gap-3 overflow-hidden rounded-sm border border-border bg-card p-6 shadow-sm',
                },
                LINHAS.map((largura, indice) =>
                    h('span', {
                        key: indice,
                        className: cn(
                            'h-2 shrink-0 rounded-full',
                            largura,
                            indice === 2 || indice === 5 ? 'bg-accent' : 'bg-muted',
                        ),
                    }),
                ),
                h('span', {
                    className:
                        'animate-varredura absolute inset-x-0 top-0 h-1/4 border-b-2 border-foreground bg-gradient-to-b from-transparent to-accent/20',
                }),
            ),
            h(
                'div',
                { className: 'flex flex-col items-center gap-1 text-center', role: 'status', 'aria-live': 'polite' },
                h('p', { className: 'text-lg font-medium' }, mensagem),
                h('p', { className: 'max-w-full text-sm leading-relaxed text-muted-foreground' }, detalhe),
                h('p', { className: 'max-w-full truncate font-mono text-sm text-muted-foreground' }, nomeArquivo),
            ),
        ),
    );
}
