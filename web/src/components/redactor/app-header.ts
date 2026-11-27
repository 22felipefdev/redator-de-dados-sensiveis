import { createElement as h } from 'react';
import { cn } from '../../lib/utils';

const ETAPAS = ['Enviar', 'Revisar', 'Baixar'] as const;

export function AppHeader({ etapaAtual }: { etapaAtual: 0 | 1 | 2 }) {
    return h(
        'header',
        {
            className:
                'flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-4 backdrop-blur-md md:px-6',
        },
        h(
            'div',
            { className: 'flex items-center gap-2.5' },
            h(
                'span',
                { 'aria-hidden': 'true', className: 'flex w-5 flex-col gap-0.5' },
                h('span', { className: 'h-1 w-full rounded-full bg-foreground/50' }),
                h('span', { className: 'h-1.5 w-4/5 bg-accent' }),
                h('span', { className: 'h-1 w-3/5 rounded-full bg-foreground/50' }),
            ),
            h('span', { className: 'text-base font-semibold tracking-tight' }, 'PrivacyDocs'),
        ),
        h(
            'nav',
            { 'aria-label': 'Etapas' },
            h(
                'ol',
                { className: 'flex items-center gap-1 md:gap-2' },
                ETAPAS.map((etapa, indice) => {
                    const ativa = indice === etapaAtual;
                    const concluida = indice < etapaAtual;
                    return h(
                        'li',
                        { key: etapa, className: 'flex items-center gap-1 md:gap-2' },
                        indice > 0
                            ? h('span', {
                                  'aria-hidden': 'true',
                                  className: cn(
                                      'h-px w-3 md:w-6',
                                      concluida || ativa ? 'bg-foreground' : 'bg-border',
                                  ),
                              })
                            : null,
                        h(
                            'span',
                            {
                                'aria-current': ativa ? 'step' : undefined,
                                className: cn(
                                    'flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium md:text-sm',
                                    ativa && 'bg-primary text-primary-foreground',
                                    concluida && 'text-foreground',
                                    !ativa && !concluida && 'text-muted-foreground',
                                ),
                            },
                            h('span', { className: 'font-mono text-[11px] opacity-70' }, String(indice + 1)),
                            h(
                                'span',
                                { className: cn(!ativa && 'hidden sm:inline') },
                                etapa,
                            ),
                        ),
                    );
                }),
            ),
        ),
    );
}
