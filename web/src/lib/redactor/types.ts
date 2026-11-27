export type TipoArquivo = 'pdf' | 'imagem' | 'texto';
export type ModoDeteccao = 'api' | 'local';
export type OrigemDado = 'api' | 'contexto' | 'local' | 'manual';

export interface Caixa {
    pagina: number;
    x: number;
    y: number;
    largura: number;
    altura: number;
}

export interface Trecho {
    texto: string;
    x: number;
    y: number;
    largura: number;
    altura: number;
}

export interface Pagina {
    canvas: HTMLCanvasElement;
    url: string;
    largura: number;
    altura: number;
    escala: number;
}

export interface PaginaVisivel {
    url: string;
    largura: number;
    altura: number;
}

export interface ReferenciaLgpd {
    id: string;
    titulo: string;
    texto: string;
    tipo: string;
    url: string;
}

export interface Dado {
    id: string;
    categoria: string;
    valor: string;
    caixas: Caixa[];
    pagina: number;
    revisar: boolean;
    origem: OrigemDado;
    // A IA só sugere: o cliente escolhe o que será censurado.
    selecionarPorPadrao: boolean;
    confianca?: number;
    referenciasLgpd: ReferenciaLgpd[];
}

export interface ItemApi {
    dado: string;
    tipo: string;
    risco: string;
    revisar: boolean;
    original: string | null;
    origem?: string;
    selecionar_por_padrao?: boolean;
    confianca?: number | null;
    referencias_lgpd?: ReferenciaLgpd[];
}

export interface Posicoes {
    largura: number;
    altura: number;
    palavras: Trecho[];
}

export interface RespostaApi {
    arquivo: string;
    posicoes: Posicoes | null;
    itens: ItemApi[];
}

export interface Resultado {
    url: string;
    nome: string;
    tamanho: number;
    areas: number;
    paginas: PaginaVisivel[];
    referencias: string[];
    texto: boolean;
}
