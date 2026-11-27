import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Junta classes Tailwind e remove as que se sobrescrevem. */
export function cn(...entradas: ClassValue[]): string {
    return twMerge(clsx(entradas));
}
