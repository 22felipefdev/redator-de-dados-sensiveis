import { createElement as h, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import { FileUp, ShieldCheck, TriangleAlert } from 'lucide-react';
import { ACEITOS } from '../../lib/redactor/document';
import { cn } from '../../lib/utils';

const DETECTADOS = [
    'CPF',
    'CNPJ',
    'RG',
    'E-mail',
    'Telefone',
    'CEP',
    'Cartão',
    'Nomes*',
    'Contexto IA*',
    'Artigos LGPD',
];

interface UploadZoneProps {
    onArquivo: (arquivo: File) => void;
    erro: string | null;
}

export function UploadZone({ onArquivo, erro }: UploadZoneProps) {
    const [arrastando, setArrastando] = useState(false);

    const aoSelecionar = (evento: ChangeEvent<HTMLInputElement>) => {
        const arquivo = evento.target.files?.[0];
        evento.target.value = '';
        if (arquivo) onArquivo(arquivo);
    };

    const aoSoltar = (evento: DragEvent<HTMLLabelElement>) => {
        evento.preventDefault();
        setArrastando(false);
        const arquivo = evento.dataTransfer.files?.[0];
        if (arquivo) onArquivo(arquivo);
    };

    return h(
        'main',
        { className: 'flex flex-1 items-center justify-center px-4 py-12 md:py-20' },
        h(
            'div',
            { className: 'flex w-full max-w-2xl flex-col gap-10' },
            h(
                'div',
                { className: 'flex flex-col gap-4' },
                h(
                    'h1',
                    { className: 'text-4xl font-semibold leading-tight tracking-tight text-balance md:text-5xl' },
                    'Envie o arquivo. Escolha o que deve ',
                    h(
                        'span',
                        { className: 'relative inline-block' },
                        h('span', { className: 'text-muted-foreground/30' }, 'desaparecer'),
                        h('span', {
                            'aria-hidden': 'true',
                            className:
                                'animate-tarja absolute -inset-x-[0.08em] top-[0.2em] bottom-[0.06em] origin-left bg-redaction',
                        }),
                    ),
                    '.',
                ),
                h(
                    'p',
                    { className: 'max-w-xl text-base leading-relaxed text-muted-foreground text-pretty' },
                    'O PrivacyDocs encontra dados sensíveis em PDF, imagem e texto, você revisa o que será coberto e recebe um arquivo novo com tarjas definitivas.',
                ),
            ),
            h(
                'label',
                {
                    onDragOver: (evento: DragEvent<HTMLLabelElement>) => {
                        evento.preventDefault();
                        setArrastando(true);
                    },
                    onDragLeave: () => setArrastando(false),
                    onDrop: aoSoltar,
                    className: cn(
                        'group flex cursor-pointer flex-col items-center gap-4 rounded-lg border-2 border-dashed bg-card px-6 py-14 text-center transition-colors',
                        'has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-offset-2 has-[:focus-visible]:ring-offset-background',
                        arrastando
                            ? 'border-accent bg-accent/10'
                            : 'border-foreground/30 hover:border-foreground/60',
                    ),
                },
                h('input', { type: 'file', accept: ACEITOS, onChange: aoSelecionar, className: 'sr-only' }),
                h(
                    'span',
                    { className: 'flex size-12 items-center justify-center rounded-md bg-primary text-primary-foreground' },
                    h(FileUp, { className: 'size-6', 'aria-hidden': 'true' }),
                ),
                h(
                    'span',
                    { className: 'flex flex-col gap-1' },
                    h(
                        'span',
                        { className: 'text-lg font-medium' },
                        arrastando
                            ? 'Solte para analisar'
                            : 'Arraste o arquivo aqui ou clique para escolher',
                    ),
                    h(
                        'span',
                        { className: 'text-sm text-muted-foreground' },
                        'PDF, PNG, JPG ou texto · até 20 MB',
                    ),
                ),
            ),
            erro
                ? h(
                      'p',
                      {
                          role: 'alert',
                          className:
                              'flex items-start gap-2 rounded-md border border-destructive/30 bg-card px-4 py-3 text-sm text-destructive',
                      },
                      h(TriangleAlert, { className: 'mt-0.5 size-4 shrink-0', 'aria-hidden': 'true' }),
                      erro,
                  )
                : null,
            h(
                'div',
                {
                    className:
                        'flex flex-col gap-4 border-t border-border pt-6 md:flex-row md:items-start md:justify-between',
                },
                h(
                    'div',
                    { className: 'flex flex-col gap-2' },
                    h(
                        'p',
                        { className: 'font-mono text-xs uppercase tracking-wider text-muted-foreground' },
                        'Detecta',
                    ),
                    h(
                        'ul',
                        { className: 'flex flex-wrap gap-1.5' },
                        DETECTADOS.map((item) =>
                            h(
                                'li',
                                {
                                    key: item,
                                    className:
                                        'rounded border border-border bg-card px-2 py-0.5 font-mono text-xs',
                                },
                                item,
                            ),
                        ),
                    ),
                    h(
                        'p',
                        { className: 'text-xs text-muted-foreground' },
                        '*Nomes e trechos contextuais dependem da API Python. A IA apenas sugere: nada é censurado sem sua confirmação.',
                    ),
                ),
                h(
                    'p',
                    {
                        className:
                            'flex max-w-60 items-start gap-2 text-sm leading-relaxed text-muted-foreground',
                    },
                    h(ShieldCheck, { className: 'mt-0.5 size-4 shrink-0 text-foreground', 'aria-hidden': 'true' }),
                    'As tarjas são aplicadas no seu navegador e o texto coberto não pode ser recuperado. Textos são apenas sinalizados.',
                ),
            ),
        ),
    );
}
