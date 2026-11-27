import type { Caixa, Dado, ItemApi, Trecho } from './types';

// Comparação tolerante a pontuação, espaços e acentos: o backend devolve o
// valor normalizado, enquanto o PDF/OCR traz o texto como está no documento.
export function normalizar(texto: string): string {
    return texto
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9@]/g, '');
}

// Confusões típicas de OCR em campos numéricos. Esta tabela serve apenas para
// localizar no documento um valor que a API já confirmou — nunca inventa dado.
const CONFUSOES_DIGITO: Record<string, string> = {
    o: '0',
    q: '0',
    d: '0',
    l: '1',
    i: '1',
    s: '5',
    b: '8',
    z: '2',
    g: '9',
    t: '7',
};

const TIPOS_NUMERICOS = new Set([
    'CPF',
    'CNPJ',
    'RG',
    'Cartão',
    'Cartão de crédito',
    'Telefone',
    'CEP',
    'Número de ofício',
]);

function digitoDe(caractere: string): string | undefined {
    const minusculo = caractere.toLowerCase();
    return /[0-9]/.test(minusculo) ? minusculo : CONFUSOES_DIGITO[minusculo];
}

function assinaturaDigitos(texto: string) {
    let assinatura = '';
    const mapa: number[] = [];
    for (let i = 0; i < texto.length; i++) {
        const digito = digitoDe(texto[i]);
        if (!digito) continue;
        assinatura += digito;
        mapa.push(i);
    }
    return { assinatura, mapa };
}

export interface IndicePagina {
    pagina: number;
    texto: string;
    trechos: Trecho[];
    inicios: number[];
    normalizado: string;
    mapa: number[];
    digitos: string;
    mapaDigitos: number[];
}

// Junta os trechos da página num texto só e guarda, para cada caractere
// normalizado, a posição original. Assim um dado quebrado em vários trechos
// ("123.456" + ".789-09") ainda é encontrado e mapeado de volta às caixas.
export function indexarPagina(pagina: number, trechos: Trecho[]): IndicePagina {
    let texto = '';
    const inicios: number[] = [];
    trechos.forEach((trecho, indice) => {
        if (indice > 0) texto += ' ';
        inicios.push(texto.length);
        texto += trecho.texto;
    });

    let normalizado = '';
    const mapa: number[] = [];
    let digitos = '';
    const mapaDigitos: number[] = [];
    for (let i = 0; i < texto.length; i++) {
        for (const caractere of normalizar(texto[i])) {
            normalizado += caractere;
            mapa.push(i);
        }
        const digito = digitoDe(texto[i]);
        if (digito) {
            digitos += digito;
            mapaDigitos.push(i);
        }
    }

    return { pagina, texto, trechos, inicios, normalizado, mapa, digitos, mapaDigitos };
}

let medidor: CanvasRenderingContext2D | null | undefined;

// Estima onde o trecho começa/termina na linha medindo o texto em fonte sem
// serifa — bem mais fiel que contar caracteres em fontes proporcionais.
function fracaoDaLargura(texto: string, posicao: number): number {
    if (medidor === undefined) {
        medidor = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d');
        if (medidor) medidor.font = '100px Helvetica, Arial, sans-serif';
    }
    if (!medidor) return posicao / texto.length;
    const total = medidor.measureText(texto).width;
    return total ? medidor.measureText(texto.slice(0, posicao)).width / total : posicao / texto.length;
}

function caixasDoIntervalo(indice: IndicePagina, inicio: number, fim: number): Caixa[] {
    const caixas: Caixa[] = [];
    indice.trechos.forEach((trecho, i) => {
        const comeco = indice.inicios[i];
        const tamanho = trecho.texto.length;
        if (!tamanho) return;
        const sobreposicaoInicio = Math.max(inicio, comeco);
        const sobreposicaoFim = Math.min(fim, comeco + tamanho);
        if (sobreposicaoFim <= sobreposicaoInicio) return;

        let fracaoInicio = fracaoDaLargura(trecho.texto, sobreposicaoInicio - comeco);
        let fracaoFim = fracaoDaLargura(trecho.texto, sobreposicaoFim - comeco);
        if (fracaoFim - fracaoInicio > 0.8) {
            fracaoInicio = 0;
            fracaoFim = 1;
        }

        // A fonte real pode diferir da usada na medição: sobra margem para não
        // deixar nenhum caractere exposto.
        const folgaX = trecho.altura * 0.4;
        const folgaY = trecho.altura * 0.22;
        caixas.push({
            pagina: indice.pagina,
            x: trecho.x + trecho.largura * fracaoInicio - folgaX,
            y: trecho.y - folgaY,
            largura: trecho.largura * (fracaoFim - fracaoInicio) + folgaX * 2,
            altura: trecho.altura + folgaY * 2,
        });
    });
    return caixas;
}

function caixasUnicas(caixas: Caixa[]): Caixa[] {
    const vistas = new Set<string>();
    const unicas: Caixa[] = [];
    for (const caixa of caixas) {
        const chave = [caixa.pagina, caixa.x, caixa.y, caixa.largura, caixa.altura]
            .map((valor) => Math.round(valor * 100) / 100)
            .join(':');
        if (vistas.has(chave)) continue;
        vistas.add(chave);
        unicas.push(caixa);
    }

    // Palavras de uma mesma frase chegam como caixas separadas; fundi-las
    // forma um destaque contínuo e evita contar "4 áreas" para 1 trecho.
    const ordenadas = [...unicas].sort(
        (a, b) => a.pagina - b.pagina || a.y - b.y || a.x - b.x,
    );
    const mescladas: Caixa[] = [];
    for (const caixa of ordenadas) {
        const alvo = mescladas.find((existente) => {
            if (existente.pagina !== caixa.pagina) return false;
            const sobreposicaoY =
                Math.min(existente.y + existente.altura, caixa.y + caixa.altura) -
                Math.max(existente.y, caixa.y);
            const minimaAltura = Math.min(existente.altura, caixa.altura);
            if (sobreposicaoY < minimaAltura * 0.5) return false;
            const sobreposicaoX =
                Math.min(existente.x + existente.largura, caixa.x + caixa.largura) -
                Math.max(existente.x, caixa.x);
            const folga = Math.max(existente.altura, caixa.altura) * 0.5;
            return sobreposicaoX > -folga;
        });

        if (!alvo) {
            mescladas.push(caixa);
            continue;
        }
        const x = Math.min(alvo.x, caixa.x);
        const y = Math.min(alvo.y, caixa.y);
        const direita = Math.max(alvo.x + alvo.largura, caixa.x + caixa.largura);
        const baixo = Math.max(alvo.y + alvo.altura, caixa.y + caixa.altura);
        alvo.x = x;
        alvo.y = y;
        alvo.largura = direita - x;
        alvo.altura = baixo - y;
    }
    return mescladas;
}

// Quando o OCR troca um dígito por letra parecida (5→S, 0→O...), a busca
// normalizada não encontra a segunda ocorrência. A assinatura de dígitos localiza
// o valor já confirmado pela API; nenhum caractere é criado ou corrigido.
function buscarPorDigitos(indice: IndicePagina, alvo: string): Caixa[] {
    const assinatura = assinaturaDigitos(alvo).assinatura;
    if (assinatura.length < 6) return [];

    const caixas: Caixa[] = [];
    let posicao = indice.digitos.indexOf(assinatura);
    while (posicao >= 0) {
        const inicio = indice.mapaDigitos[posicao];
        const fim = indice.mapaDigitos[posicao + assinatura.length - 1] + 1;
        // A borda precisa ser avaliada no texto original: na assinatura os
        // espaços desaparecem e números vizinhos pareceriam colados.
        const anterior = inicio > 0 ? indice.texto[inicio - 1] : '';
        const posterior = indice.texto[fim] ?? '';
        if (!/[0-9a-z]/i.test(anterior) && !/[0-9a-z]/i.test(posterior)) {
            caixas.push(...caixasDoIntervalo(indice, inicio, fim));
        }
        posicao = indice.digitos.indexOf(assinatura, posicao + 1);
    }
    return caixas;
}

function buscar(indice: IndicePagina, alvo: string, categoria?: string): Caixa[] {
    const alvoNormalizado = normalizar(alvo);
    if (alvoNormalizado.length < 4) return [];

    const encontradas: Caixa[] = [];
    let posicao = indice.normalizado.indexOf(alvoNormalizado);
    while (posicao >= 0) {
        const inicio = indice.mapa[posicao];
        const fim = indice.mapa[posicao + alvoNormalizado.length - 1] + 1;
        encontradas.push(...caixasDoIntervalo(indice, inicio, fim));
        posicao = indice.normalizado.indexOf(alvoNormalizado, posicao + alvoNormalizado.length);
    }

    if (!categoria || !TIPOS_NUMERICOS.has(categoria)) return caixasUnicas(encontradas);
    return caixasUnicas([...encontradas, ...buscarPorDigitos(indice, alvo)]);
}

// A origem "contexto" vem da IA: nunca entra marcada por padrão.
function origemDoItem(item: ItemApi): Dado['origem'] {
    return item.origem === 'contexto' ? 'contexto' : 'api';
}

function comunDoItem(item: ItemApi, id: string, caixas: Caixa[], pagina: number): Dado {
    return {
        id,
        categoria: item.tipo,
        valor: item.dado,
        caixas,
        pagina,
        revisar: item.revisar || caixas.length === 0,
        origem: origemDoItem(item),
        selecionarPorPadrao: item.selecionar_por_padrao ?? true,
        confianca: item.confianca ?? undefined,
        referenciasLgpd: item.referencias_lgpd ?? [],
    };
}

export function detectarComApi(itens: ItemApi[], indices: IndicePagina[]): Dado[] {
    return itens.map((item, i) => {
        const candidatos = [item.original, item.dado].filter((valor): valor is string => Boolean(valor));
        const caixas: Caixa[] = [];
        for (const indice of indices) {
            for (const candidato of candidatos) {
                // `original` e `dado` podem capturar ocorrências diferentes: não
                // parar no primeiro que der match evita perder uma repetição.
                caixas.push(...buscar(indice, candidato, item.tipo));
            }
        }
        const unicas = caixasUnicas(caixas);
        return comunDoItem(item, `api-${i}`, unicas, unicas[0]?.pagina ?? 0);
    });
}

// Arquivos de texto só sinalizam: não há como aplicar tarjas sem reconstruir o
// conteúdo, então o original volta intacto e a decisão fica com o cliente.
export function itensParaTexto(itens: ItemApi[]): Dado[] {
    return itens.map((item, i) => comunDoItem(item, `texto-${i}`, [], 0));
}

function cpfValido(digitos: string): boolean {
    if (digitos.length !== 11 || /^(\d)\1+$/.test(digitos)) return false;
    const calcular = (quantidade: number) => {
        let soma = 0;
        for (let i = 0; i < quantidade; i++) soma += Number(digitos[i]) * (quantidade + 1 - i);
        const resto = (soma * 10) % 11;
        return resto === 10 ? 0 : resto;
    };
    return calcular(9) === Number(digitos[9]) && calcular(10) === Number(digitos[10]);
}

const PADROES: { categoria: string; regex: RegExp; validar?: (valor: string) => boolean }[] = [
    { categoria: 'E-mail', regex: /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g },
    { categoria: 'CNPJ', regex: /\b\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}\b/g },
    { categoria: 'CPF', regex: /\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/g },
    {
        categoria: 'CPF',
        regex: /\b\d{11}\b/g,
        validar: (valor) => cpfValido(valor),
    },
    { categoria: 'Cartão', regex: /\b(?:\d{4}[ -]){3}\d{4}\b/g },
    { categoria: 'RG', regex: /\b\d{1,2}\.\d{3}\.\d{3}-[\dXx]\b/g },
    {
        categoria: 'Telefone',
        regex: /(?:\+55\s?)?(?:\(\d{2}\)\s?|\b\d{2}\s)(?:9\s?)?\d{4}[-\s]?\d{4}\b|\b9?\d{4}-\d{4}\b/g,
    },
    { categoria: 'CEP', regex: /\b\d{5}-\d{3}\b/g },
];

// Usado quando a API Python não está disponível: cobre os formatos brasileiros
// mais comuns direto no texto do PDF.
export function detectarLocalmente(indices: IndicePagina[]): Dado[] {
    const agrupados = new Map<string, Dado>();

    for (const indice of indices) {
        const ocupados: [number, number][] = [];
        for (const padrao of PADROES) {
            for (const encontro of indice.texto.matchAll(padrao.regex)) {
                const inicio = encontro.index ?? 0;
                const fim = inicio + encontro[0].length;
                if (ocupados.some(([a, b]) => inicio < b && fim > a)) continue;
                if (padrao.validar && !padrao.validar(encontro[0])) continue;
                ocupados.push([inicio, fim]);

                const valor = encontro[0].trim();
                const chave = `${padrao.categoria}|${normalizar(valor)}`;
                const existente = agrupados.get(chave);
                const caixas = caixasDoIntervalo(indice, inicio, fim);
                if (existente) {
                    existente.caixas.push(...caixas);
                } else {
                    agrupados.set(chave, {
                        id: `local-${agrupados.size}`,
                        categoria: padrao.categoria,
                        valor,
                        caixas,
                        pagina: caixas[0]?.pagina ?? 0,
                        revisar: false,
                        origem: 'local',
                        selecionarPorPadrao: true,
                        referenciasLgpd: [],
                    });
                }
            }
        }
    }

    return [...agrupados.values()];
}
