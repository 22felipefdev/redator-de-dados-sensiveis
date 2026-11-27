import { createElement as h } from 'react';
import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export type Variante = 'default' | 'outline' | 'secondary' | 'ghost' | 'link' | 'destructive';
export type Tamanho = 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm';

const BASE =
    'inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent text-sm font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50';
const VARIANTES: Record<Variante, string> = {
    default: 'bg-primary text-primary-foreground hover:bg-primary/80',
    outline: 'border-border bg-background hover:bg-muted',
    secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
    ghost: 'hover:bg-muted',
    link: 'text-primary underline-offset-4 hover:underline',
    destructive: 'bg-destructive/10 text-destructive hover:bg-destructive/20',
};
const TAMANHOS: Record<Tamanho, string> = {
    default: 'h-8 gap-1.5 px-2.5',
    sm: 'h-7 gap-1 px-2.5 text-[0.8rem]',
    lg: 'h-9 gap-1.5 px-2.5',
    icon: 'size-8',
    'icon-sm': 'size-7',
};

export interface BotaoProps {
    children?: ReactNode;
    className?: string;
    variant?: Variante;
    size?: Tamanho;
    onClick?: () => void;
    disabled?: boolean;
    ariaLabel?: string;
    ariaPressed?: boolean;
    title?: string;
    href?: string;
    download?: string;
    target?: string;
    rel?: string;
}

/** Botão simples no estilo shadcn, sem JSX e sem dependências extras. */
export function Botao({
    children,
    className,
    variant = 'default',
    size = 'default',
    onClick,
    disabled,
    ariaLabel,
    ariaPressed,
    title,
    href,
    download,
    target,
    rel,
}: BotaoProps) {
    if (href) {
        return h(
            'a',
            {
                href,
                download,
                target,
                rel,
                className: cn(BASE, VARIANTES[variant], TAMANHOS[size], className),
                'aria-label': ariaLabel,
                title,
            },
            children,
        );
    }

    return h(
        'button',
        {
            type: 'button',
            className: cn(BASE, VARIANTES[variant], TAMANHOS[size], className),
            onClick,
            disabled,
            'aria-label': ariaLabel,
            'aria-pressed': ariaPressed,
            title,
        },
        children,
    );
}
