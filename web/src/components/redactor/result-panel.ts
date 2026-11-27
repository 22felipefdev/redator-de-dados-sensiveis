import { createElement as h } from 'react';
import { ArrowLeft, Download, ExternalLink, FilePlus2, ShieldCheck } from 'lucide-react';
import { Botao } from './button';
import type { Resultado } from '../../lib/redactor/types';

function formatarTamanho(bytes: number) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
}

interface ResultPanelProps {
    resultado: Resultado;
    referencias: string[];
    onVoltar: () => void;
    onNovo: () => void;
}

export function ResultPanel({ resultado, referencias, onVoltar, onNovo }: ResultPanelProps) {
    const detalhes: [string, string][] = [
        ['Arquivo', resultado.nome],
        [resultado.texto ? 'Dados sinalizados' : 'Áreas cobertas', String(resultado.areas)],
        ['Páginas', String(resultado.paginas.length)],
        ['Tamanho', formatarTamanho(resultado.tamanho)],
    ];

    return h(
        'aside',
        { className: 'flex flex-col border-t border-border bg-card lg:min-h-0 lg:border-t-0 lg:border-l' },
        h(
            'div',
            { className: 'flex flex-col gap-5 px-5 py-6 lg:flex-1 lg:overflow-y-auto' },
            h(
                'div',
                { className: 'flex flex-col gap-1' },
                h(
                    'h2',
                    { className: 'text-lg font-semibold tracking-tight' },
                    resultado.texto ? 'Arquivo de texto sinalizado' : 'Documento censurado',
                ),
                h(
                    'p',
                    { className: 'text-sm leading-relaxed text-muted-foreground' },
                    resultado.texto
                        ? 'O conteúdo original volta sem alterações: tarjas não se aplicam a arquivos de texto.'
                        : 'Esta é a pré-visualização do arquivo novo, exatamente como será baixado.',
                ),
            ),
            h(
                'dl',
                { className: 'flex flex-col divide-y divide-border rounded-md border border-border' },
                detalhes.map(([rotulo, valor]) =>
                    h(
                        'div',
                        {
                            key: rotulo,
                            className: 'flex items-baseline justify-between gap-4 px-3 py-2.5 text-sm',
                        },
                        h('dt', { className: 'text-muted-foreground' }, rotulo),
                        h('dd', { className: 'min-w-0 truncate font-mono', title: valor }, valor),
                    ),
                ),
            ),
            referencias.length > 0
                ? h(
                      'section',
                      null,
                      h(
                          'h3',
                          {
                              className:
                                  'mb-2 font-mono text-[11px] font-medium uppercase tracking-wider text-muted-foreground',
                          },
                          'Referências LGPD',
                      ),
                      h(
                          'ul',
                          { className: 'flex flex-col gap-1.5' },
                          referencias.map((referencia) =>
                              h(
                                  'li',
                                  {
                                      key: referencia,
                                      className: 'rounded bg-muted px-3 py-2 text-xs leading-relaxed',
                                  },
                                  referencia,
                              ),
                          ),
                      ),
                  )
                : null,
            h(
                'p',
                { className: 'flex items-start gap-2 text-sm leading-relaxed text-muted-foreground' },
                h(ShieldCheck, { className: 'mt-0.5 size-4 shrink-0 text-foreground', 'aria-hidden': 'true' }),
                resultado.texto
                    ? 'O texto original é devolvido sem alterações. Use as referências para revisar manualmente.'
                    : 'As páginas foram convertidas em imagem com as tarjas aplicadas: o texto coberto não pode ser copiado nem recuperado.',
            ),
        ),
        h(
            'div',
            { className: 'sticky bottom-0 flex flex-col gap-2 border-t border-border bg-card px-5 py-4 backdrop-blur-xl' },
            h(
                Botao,
                {
                    size: 'lg',
                    className: 'h-11 w-full text-base',
                    href: resultado.url,
                    download: resultado.nome,
                },
                h(Download, { 'aria-hidden': 'true' }),
                'Baixar arquivo',
            ),
            h(
                Botao,
                {
                    variant: 'outline',
                    size: 'lg',
                    className: 'h-10 w-full',
                    href: resultado.url,
                    target: '_blank',
                    rel: 'noreferrer',
                },
                h(ExternalLink, { 'aria-hidden': 'true' }),
                'Abrir em nova aba',
            ),
            h(
                'div',
                { className: 'grid grid-cols-2 gap-2' },
                h(
                    Botao,
                    { variant: 'ghost', size: 'lg', className: 'h-10', onClick: onVoltar },
                    h(ArrowLeft, { 'aria-hidden': 'true' }),
                    'Ajustar',
                ),
                h(
                    Botao,
                    { variant: 'ghost', size: 'lg', className: 'h-10', onClick: onNovo },
                    h(FilePlus2, { 'aria-hidden': 'true' }),
                    'Novo arquivo',
                ),
            ),
        ),
    );
}
