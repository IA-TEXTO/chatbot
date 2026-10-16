"""Memória limitada aos snapshots documentais da ramificação recebida."""

import re
from dataclasses import dataclass, field

from chat.rag import RetrievedChunk

MAX_MENSAGENS_MEMORIA = 12
MAX_FONTES_MEMORIA = 4
MAX_CARACTERES_MEMORIA = 6000
CITACAO = re.compile(r'\[Fonte\s+(\d+)\]', re.I)


def chave_fonte(fonte):
    return fonte.documento_id, fonte.conteudo


def ler_fonte(dados):
    if not isinstance(dados, dict):
        return None
    for campo in ['documento_id', 'numero']:
        if type(dados.get(campo)) is not int or dados[campo] <= 0:
            return None
    if not all(
        isinstance(dados.get(campo), str)
        for campo in ['nome', 'tipo', 'trecho']
    ):
        return None
    if not dados['trecho'].strip():
        return None
    return RetrievedChunk(
        documento_id=dados['documento_id'],
        documento_nome=dados['nome'],
        documento_tipo=dados['tipo'],
        conteudo=dados['trecho'],
        score=0,
    )


@dataclass
class EvidenceMemory:
    fontes: list[RetrievedChunk] = field(default_factory=list)

    @classmethod
    def from_messages(cls, mensagens):
        fontes = []
        chaves = set()
        caracteres = 0
        for mensagem in reversed(list(mensagens)[-MAX_MENSAGENS_MEMORIA:]):
            if mensagem.tipo != 'ASSISTENTE':
                continue
            citadas = {int(n) for n in CITACAO.findall(mensagem.conteudo)}
            for grupo in re.findall(
                r'\(fontes?\s+\d+(?:\s*,\s*\d+)*\)', mensagem.conteudo, re.I
            ):
                citadas.update(int(n) for n in re.findall(r'\d+', grupo))
            dados_fontes = getattr(mensagem, 'fontes', None)
            if not isinstance(dados_fontes, list):
                continue
            # Fontes efetivamente citadas têm prioridade sobre trechos só recuperados.
            candidatas = sorted(
                (
                    dados
                    for dados in dados_fontes
                    if ler_fonte(dados) is not None
                ),
                key=lambda dados: dados.get('numero') not in citadas,
            )
            for dados in candidatas:
                fonte = ler_fonte(dados)
                if fonte is None or chave_fonte(fonte) in chaves:
                    continue
                if len(fontes) >= MAX_FONTES_MEMORIA:
                    return cls(fontes)
                if caracteres + len(fonte.conteudo) > MAX_CARACTERES_MEMORIA:
                    continue
                chaves.add(chave_fonte(fonte))
                caracteres += len(fonte.conteudo)
                fontes.append(fonte)
        return cls(fontes)

    def format_for_triage(self):
        if not self.fontes:
            return ''
        return (
            '\n\n<evidencias_anteriores_dados>\n'
            + '\n\n'.join(
                f'Documento: {f.documento_nome}\nTrecho: {f.conteudo}'
                for f in self.fontes
            )
            + '\n</evidencias_anteriores_dados>'
        )


def remap_history_citations(mensagem, fontes):
    """Números de fontes só têm significado dentro da mensagem original."""
    numeros = {chave_fonte(fonte): n for n, fonte in enumerate(fontes, 1)}
    anteriores = {}
    dados_fontes = getattr(mensagem, 'fontes', None)
    for dados in dados_fontes if isinstance(dados_fontes, list) else []:
        fonte = ler_fonte(dados)
        if fonte is not None:
            anteriores[dados['numero']] = numeros.get(chave_fonte(fonte))

    def substituir(match):
        numero = anteriores.get(int(match.group(1)))
        return (
            f'[Fonte {numero}]'
            if numero
            else '[fonte anterior fora do contexto atual]'
        )

    texto = CITACAO.sub(substituir, mensagem.conteudo)

    def grupo(match):
        return (
            '('
            + ', '.join(
                substituir(CITACAO.fullmatch(f'[Fonte {n}]'))
                for n in re.findall(r'\d+', match.group(0))
            )
            + ')'
        )

    return re.sub(
        r'\(fontes?\s+\d+(?:\s*,\s*\d+)*\)', grupo, texto, flags=re.I
    )
