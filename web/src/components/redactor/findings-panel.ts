import { createElement as h } from 'react';
import { Crosshair, Loader2, SquareDashedMousePointer, X } from 'lucide-react';
import { Botao } from './button';
import type { Dado, ModoDeteccao, TipoArquivo } from '../../lib/redactor/types';
import { cn } from '../../lib/utils';

function paginasDe(dado: Dado) {
    const paginas = [...new Set(dado.caixas.map((caixa) => caixa.pagina + 1))];
    return paginas.length ? `p. ${paginas.join(', ')}` : null;
}

interface FindingsPanelProps {
    nomeArquivo: string;
    tipo: TipoArquivo;
    modo: ModoDeteccao;
    dados: Dado[];
    selecionados: Set<string>;
    modoDesenho: boolean;
    gerando: boolean;
    erro: string | null;
    onAlternar: (id: string) => void;
    onTodos: (marcar: boolean) => void;
    onLocalizar: (id: string) => void;
    onRemover: (id: string) => void;
    onModoDesenho: (ativo: boolean) => void;
    onGerar: () => void;
    onCancelar: () => void;
}

export function FindingsPanel({
    nomeArquivo,
    tipo,
    modo,
    dados,
    selecionados,
    modoDesenho,
    gerando,
    erro,
    onAlternar,
    onTodos,
    onLocalizar,
    onRemover,
    onModoDesenho,
    onGerar,
    onCancelar,
}: FindingsPanelProps) {
    const grupos = new Map<string, Dado[]>();
    for (const dado of dados) {
        grupos.set(dado.categoria, [...(grupos.get(dado.categoria) ?? []), dado]);
    }

    const areas = dados
        .filter((dado) => selecionados.has(dado.id))
        .reduce((total, dado) => total + dado.caixas.length, 0);
    const todosMarcados = dados.length > 0 && dados.every((dado) => selecionados.has(dado.id));
    const sugestoesIa = dados.filter((dado) => dado.origem === 'contexto').length;

    const aviso =
        tipo === 'texto'
            ? 'Arquivo de texto: o original volta sem alterações. As referências LGPD ajudam na revisão manual.'
            : modo === 'api'
              ? tipo === 'imagem'
                ? 'API: OCR com coordenadas e regex/Presidio decidem; a IA só sugere trechos desmarcados.'
                : 'API: regex/Presidio decidem sobre o texto do PDF; a IA só sugere trechos desmarcados.'
              : 'API indisponível: detecção local por padrões (CPF, e-mail, telefone…).';

    const rotuloGerar =
        tipo === 'texto'
            ? 'Baixar arquivo original'
            : `Gerar ${tipo === 'pdf' ? 'PDF' : 'imagem'} censurad${tipo === 'pdf' ? 'o' : 'a'}${areas ? ` · ${areas} ${areas === 1 ? 'área' : 'áreas'}` : ''}`;

    return h(
        'aside',
        { className: 'flex flex-col border-t border-border bg-card lg:min-h-0 lg:border-t-0 lg:border-l' },
        h(
            'div',
            { className: 'flex flex-col gap-3 border-b border-border px-5 py-4' },
            h(
                'div',
                { className: 'flex items-start justify-between gap-3' },
                h(
                    'div',
                    { className: 'flex min-w-0 flex-col gap-0.5' },
                    h('h2', { className: 'text-lg font-semibold tracking-tight' }, 'Dados encontrados'),
                    h(
                        'p',
                        { className: 'truncate font-mono text-xs text-muted-foreground', title: nomeArquivo },
                        nomeArquivo,
                    ),
                ),
                h(
                    Botao,
                    {
                        variant: 'ghost',
                        size: 'icon-sm',
                        onClick: onCancelar,
                        ariaLabel: 'Descartar e enviar outro arquivo',
                    },
                    h(X, { 'aria-hidden': 'true' }),
                ),
            ),
            h(
                'p',
                {
                    className: cn(
                        'rounded px-2.5 py-1.5 text-xs leading-relaxed',
                        modo === 'api'
                            ? 'bg-muted text-muted-foreground'
                            : 'bg-accent/10 text-foreground ring-1 ring-accent/40',
                    ),
                },
                aviso,
            ),
        ),
        h(
            'div',
            { className: 'flex items-center justify-between gap-2 px-5 py-3 text-sm' },
            h(
                'span',
                { className: 'text-muted-foreground' },
                h('span', { className: 'font-medium text-foreground' }, String(selecionados.size)),
                ' de ',
                dados.length,
                ' marcados',
            ),
            dados.length > 0
                ? h(
                      Botao,
                      { variant: 'link', size: 'sm', className: 'px-0', onClick: () => onTodos(!todosMarcados) },
                      todosMarcados ? 'Desmarcar todos' : 'Marcar todos',
                  )
                : null,
        ),
        h(
            'div',
            { className: 'flex flex-col gap-5 px-5 pb-5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto' },
            sugestoesIa > 0
                ? h(
                      'p',
                      { className: 'rounded-md bg-accent/10 px-3 py-2 text-xs leading-relaxed text-foreground' },
                      `${sugestoesIa} sugestão(ões) da IA aguardando sua revisão. Elas entram desmarcadas: marque só o que deve ser censurado.`,
                  )
                : null,
            dados.length === 0
                ? h(
                      'p',
                      {
                          className:
                              'rounded-md border border-dashed border-border px-4 py-6 text-center text-sm leading-relaxed text-muted-foreground',
                      },
                      'Nenhum dado sensível foi encontrado automaticamente. Use ',
                      h('span', { className: 'font-medium text-foreground' }, 'Desenhar área'),
                      ' para cobrir trechos manualmente.',
                  )
                : null,
            [...grupos.entries()].map(([categoria, itens]) =>
                h(
                    'section',
                    {
                        key: categoria,
                        className: 'flex flex-col gap-1.5',
                        'aria-labelledby': `grupo-${categoria}`,
                    },
                    h(
                        'h3',
                        {
                            id: `grupo-${categoria}`,
                            className:
                                'flex items-center justify-between font-mono text-[11px] font-medium uppercase tracking-wider text-muted-foreground',
                        },
                        categoria,
                        h('span', null, String(itens.length)),
                    ),
                    h(
                        'ul',
                        { className: 'flex flex-col' },
                        itens.map((dado) => {
                            const marcado = selecionados.has(dado.id);
                            const paginas = paginasDe(dado);
                            return h(
                                'li',
                                {
                                    key: dado.id,
                                    className:
                                        'group flex items-center gap-1 rounded-md border-b border-border/60 last:border-b-0 hover:bg-muted/60',
                                },
                                h(
                                    'label',
                                    { className: 'flex min-w-0 flex-1 cursor-pointer items-start gap-3 px-2 py-2.5' },
                                    h('input', {
                                        type: 'checkbox',
                                        checked: marcado,
                                        onChange: () => onAlternar(dado.id),
                                        className: 'mt-0.5 size-4 shrink-0 cursor-pointer accent-[var(--primary)]',
                                    }),
                                    h(
                                        'span',
                                        { className: 'flex min-w-0 flex-col gap-1' },
                                        h(
                                            'span',
                                            {
                                                className: cn(
                                                    'break-all font-mono text-sm leading-snug',
                                                    marcado &&
                                                        'bg-redaction text-foreground [box-decoration-break:clone] px-1 -mx-1',
                                                ),
                                            },
                                            dado.valor,
                                        ),
                                        h(
                                            'span',
                                            { className: 'flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground' },
                                            paginas ??
                                            (tipo === 'texto'
                                                ? h('span', null, 'sinalizado (sem tarja em texto)')
                                                : h(
                                                      'span',
                                                      { className: 'text-destructive' },
                                                      'sem posição no documento',
                                                  )),
                                            dado.origem === 'contexto'
                                                ? h(
                                                      'span',
                                                      {
                                                          className:
                                                              'rounded bg-accent px-1.5 py-px font-medium text-accent-foreground',
                                                      },
                                                      'IA',
                                                  )
                                                : null,
                                            dado.referenciasLgpd.length > 0
                                                ? h(
                                                      'span',
                                                      { className: 'rounded bg-muted px-1.5 py-px' },
                                                      `${dado.referenciasLgpd.length} artigo(s) LGPD`,
                                                  )
                                                : null,
                                            dado.revisar && dado.caixas.length > 0
                                                ? h(
                                                      'span',
                                                      {
                                                          className:
                                                              'rounded bg-accent px-1.5 py-px font-medium text-accent-foreground',
                                                      },
                                                      'revisar',
                                                  )
                                                : null,
                                        ),
                                    ),
                                ),
                                dado.caixas.length > 0
                                    ? h(
                                          Botao,
                                          {
                                              variant: 'ghost',
                                              size: 'icon-sm',
                                              onClick: () => onLocalizar(dado.id),
                                              ariaLabel: `Localizar ${dado.valor} no documento`,
                                          },
                                          h(Crosshair, { 'aria-hidden': 'true' }),
                                      )
                                    : null,
                                dado.origem === 'manual'
                                    ? h(
                                          Botao,
                                          {
                                              variant: 'ghost',
                                              size: 'icon-sm',
                                              onClick: () => onRemover(dado.id),
                                              ariaLabel: `Remover ${dado.valor}`,
                                          },
                                          h(X, { 'aria-hidden': 'true' }),
                                      )
                                    : null,
                            );
                        }),
                    ),
                ),
            ),
        ),
        h(
            'div',
            { className: 'sticky bottom-0 flex flex-col gap-2 border-t border-border bg-card px-5 py-4 backdrop-blur-xl' },
            erro ? h('p', { role: 'alert', className: 'text-sm text-destructive' }, erro) : null,
            tipo === 'texto'
                ? null
                : h(
                      Botao,
                      {
                          variant: modoDesenho ? 'secondary' : 'outline',
                          size: 'lg',
                          className: cn('h-10 w-full', modoDesenho && 'ring-2 ring-accent'),
                          onClick: () => onModoDesenho(!modoDesenho),
                          ariaPressed: modoDesenho,
                      },
                      h(SquareDashedMousePointer, { 'aria-hidden': 'true' }),
                      modoDesenho ? 'Concluir desenho' : 'Desenhar área',
                  ),
            h(
                Botao,
                {
                    size: 'lg',
                    className: 'h-11 w-full text-base',
                    disabled: (tipo === 'texto' ? false : areas === 0) || gerando,
                    onClick: onGerar,
                },
                gerando ? h(Loader2, { className: 'animate-spin', 'aria-hidden': 'true' }) : null,
                gerando ? 'Aplicando tarjas…' : rotuloGerar,
            ),
        ),
    );
}
