export * from "./djangoForm";

type FileField = {
    name: string;
    url: string;
}

export type Documento = {
    id: number;
    nome: string;
    arquivo: FileField;
    status: 'pendente' | 'processando' | 'processado' | 'erro';
    tipo: 'legislacao' | 'manual';
}

export type Skill = {
    id: number;
    nome: string;
    arquivo: string;
    titulo: string;
    status: 'gerando' | 'rascunho' | 'ativa' | 'erro';
    conteudo: string;
    observacoes: string;
    arquivo_origem: string | null;
}

export type Usuario = {
    id: number;
    name: string;
    email: string;
    is_staff: boolean;
}

export type Conversa = {
    id: number;
    nome: string;
}

export type PerguntaCanonica = {
    id: number;
    pergunta: string;
    embedding: string;
    resposta: string;
}