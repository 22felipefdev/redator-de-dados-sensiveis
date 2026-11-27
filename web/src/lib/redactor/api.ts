import type { RespostaApi } from './types';

const STATUS_INDISPONIVEL = [404, 502, 504];

/**
 * Chama a API Python. Retorna null quando ela não está acessível para o app
 * cair na detecção local. `aoAvisar` avisa depois de 12 s que a IA está lenta;
 * o abort em 90 s protege a página de ficar presa.
 */
export async function analisarNaApi(
    arquivo: File,
    aoAvisar?: () => void,
): Promise<RespostaApi | null> {
    const controlador = new AbortController();
    const temporizador = window.setTimeout(() => controlador.abort(), 90_000);
    const aviso = window.setTimeout(() => aoAvisar?.(), 12_000);

    try {
        const formulario = new FormData();
        formulario.append('arquivo', arquivo);

        const resposta = await fetch('/api/analisar', {
            method: 'POST',
            body: formulario,
            signal: controlador.signal,
        });

        if (STATUS_INDISPONIVEL.includes(resposta.status)) return null;
        if (!resposta.headers.get('content-type')?.includes('application/json')) return null;

        if (!resposta.ok) {
            const corpo = (await resposta.json().catch(() => null)) as { detail?: string } | null;
            throw new Error(corpo?.detail ?? `A API respondeu com erro ${resposta.status}.`);
        }

        return (await resposta.json()) as RespostaApi;
    } catch (erro) {
        if (erro instanceof DOMException && erro.name === 'AbortError') {
            throw new DOMException('O servidor demorou mais que o esperado.', 'AbortError');
        }
        // Sem rede, ainda é possível detectar padrões no navegador.
        if (erro instanceof TypeError) return null;
        throw erro;
    } finally {
        window.clearTimeout(temporizador);
        window.clearTimeout(aviso);
    }
}
