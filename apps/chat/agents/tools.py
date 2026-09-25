"""Ferramentas de consulta usadas pelos especialistas em uma execução."""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from time import monotonic
from typing import Callable

from agno.run import RunContext
from django.db.models import Q

from chat.models import Documento, RespostaCanonica
from chat.rag import RetrievedChunk, normalize

logger = logging.getLogger(__name__)
MAX_FONTES = 18
MAX_BUSCAS_ADICIONAIS = 2
MIN_TERMO = 4
MIN_TERMOS_EM_COMUM = 2
MIN_SEMELHANCA = 0.82


@dataclass
class EvidenceContext:
    """Mantém fontes e limites isolados por pergunta, mesmo com agentes globais."""

    fontes: list[RetrievedChunk]
    tipos: tuple[str, ...]
    retriever: Callable
    on_sources: Callable[[list[dict]], None] | None = None
    on_progress: Callable[[str], None] | None = None
    buscas_adicionais: int = 0
    consultas_canonicas: int = 0
    _indices: set[tuple[int, str]] = field(default_factory=set)

    def __post_init__(self):
        self._indices = {(f.documento_id, f.conteudo) for f in self.fontes}
        self.publicar_fontes()

    def publicar_fontes(self):
        if self.on_sources:
            self.on_sources([
                {
                    'numero': indice,
                    'documento_id': fonte.documento_id,
                    'nome': fonte.documento_nome,
                    'tipo': fonte.documento_tipo,
                    'trecho': fonte.conteudo,
                }
                for indice, fonte in enumerate(self.fontes, start=1)
            ])

    def buscar(self, pergunta: str, tipo: str = 'ambos') -> dict:
        pergunta = pergunta.strip()[:300]
        if not pergunta:
            return {'erro': 'Informe o assunto da busca.'}
        if self.buscas_adicionais >= MAX_BUSCAS_ADICIONAIS:
            return {'erro': 'Limite de buscas adicionais atingido.'}
        if tipo not in {
            'ambos',
            Documento.Tipo.MANUAL,
            Documento.Tipo.LEGISLACAO,
        }:
            return {'erro': 'Tipo inválido. Use ambos, manual ou legislacao.'}
        tipos = self.tipos if tipo == 'ambos' else (tipo,)
        if any(item not in self.tipos for item in tipos):
            return {'erro': 'Esse tipo de documento não está nesta rota.'}
        self.buscas_adicionais += 1
        if self.on_progress:
            self.on_progress(
                'Fazendo uma busca complementar nos documentos...'
            )
        novos = []
        for fonte in self.retriever(pergunta, 6, tipos):
            chave = (fonte.documento_id, fonte.conteudo)
            if chave not in self._indices and len(self.fontes) < MAX_FONTES:
                self._indices.add(chave)
                self.fontes.append(fonte)
                novos.append({
                    'numero': len(self.fontes),
                    'documento': fonte.documento_nome,
                    'tipo': fonte.documento_tipo,
                    'trecho': fonte.conteudo,
                })
        self.publicar_fontes()
        if self.on_progress:
            self.on_progress(
                'Elaborando orientação com as fontes encontradas...'
            )
        return {'fontes_novas': novos, 'total_fontes': len(self.fontes)}

    def trecho(self, numero: int) -> dict:
        if numero < 1 or numero > len(self.fontes):
            return {'erro': 'Fonte não encontrada nesta resposta.'}
        fonte = self.fontes[numero - 1]
        return {
            'numero': numero,
            'documento': fonte.documento_nome,
            'tipo': fonte.documento_tipo,
            'trecho': fonte.conteudo,
        }

    def canonica(self, pergunta: str) -> dict:
        if self.consultas_canonicas >= 1:
            return {'erro': 'Consulta a respostas canônicas já realizada.'}
        self.consultas_canonicas += 1
        if self.on_progress:
            self.on_progress('Consultando orientações revisadas...')
        termos = [
            termo
            for termo in normalize(pergunta).split()
            if len(termo) >= MIN_TERMO
        ]
        if not termos:
            return {'respostas': []}
        filtro = Q()
        for termo in sorted(set(termos), key=len, reverse=True)[:3]:
            filtro |= Q(pergunta__icontains=termo)
        candidatas = RespostaCanonica.objects.filter(filtro).values(
            'pergunta', 'resposta'
        )[:200]
        consulta = normalize(pergunta)
        encontradas = []
        for item in candidatas:
            referencia = normalize(item['pergunta'])
            termos_ref = set(referencia.split())
            termos_em_comum = len(set(termos) & termos_ref)
            cobertura = termos_em_comum / max(len(set(termos)), 1)
            semelhanca = SequenceMatcher(None, consulta, referencia).ratio()
            pontuacao = max(
                cobertura if termos_em_comum >= MIN_TERMOS_EM_COMUM else 0, semelhanca
            )
            if pontuacao >= MIN_SEMELHANCA:
                encontradas.append((pontuacao, item))
        encontradas.sort(key=lambda item: item[0], reverse=True)
        if self.on_progress:
            self.on_progress('Conferindo as orientações e os documentos...')
        return {
            'respostas': [
                {'pergunta': item['pergunta'], 'orientacao': item['resposta']}
                for _, item in encontradas[:2]
            ],
            'aviso': 'Orientações revisadas não substituem as fontes documentais.',
        }


def _contexto(run_context: RunContext) -> EvidenceContext:
    contexto = (run_context.dependencies or {}).get('evidence_context')
    if not isinstance(contexto, EvidenceContext):
        raise ValueError('Contexto documental indisponível nesta execução.')
    return contexto


def buscar_fontes(
    pergunta: str, tipo: str = 'ambos', *, run_context: RunContext
) -> dict:
    """Busque até seis trechos adicionais quando as fontes iniciais não bastarem.

    Args:
        pergunta: Busca curta e específica sobre o CAR.
        tipo: ambos, manual ou legislacao, conforme a rota permitida.
    """
    return _contexto(run_context).buscar(pergunta, tipo)


def consultar_trecho(numero: int, *, run_context: RunContext) -> dict:
    """Consulte o documento e texto completo de uma Fonte N já recuperada."""
    return _contexto(run_context).trecho(numero)


def consultar_resposta_canonica(
    pergunta: str, *, run_context: RunContext
) -> dict:
    """Procure orientações revisadas para uma dúvida semelhante sobre o CAR."""
    return _contexto(run_context).canonica(pergunta)


def registrar_chamada_ferramenta(function_name, function_call, arguments):
    """Registra duração sem gravar perguntas ou trechos potencialmente sensíveis."""
    inicio = monotonic()
    try:
        return function_call(**arguments)
    finally:
        logger.info(
            'Ferramenta %s executada em %.2fs',
            function_name,
            monotonic() - inicio,
        )


def validar_citacoes(resposta: str, total_fontes: int) -> str:
    """Identifica citações inexistentes sem fingir que elas têm suporte."""
    invalidas = False

    def substituir(marcador):
        nonlocal invalidas
        numero = int(marcador.group(1))
        if 1 <= numero <= total_fontes:
            return marcador.group(0)
        invalidas = True
        return '[citação não verificada]'

    resposta = re.sub(r'\[Fonte\s+(\d+)\]', substituir, resposta, flags=re.I)

    def grupo(marcador):
        nonlocal invalidas
        numeros = [
            int(numero) for numero in re.findall(r'\d+', marcador.group(0))
        ]
        if all(1 <= numero <= total_fontes for numero in numeros):
            return marcador.group(0)
        invalidas = True
        validos = list(
            dict.fromkeys(
                numero for numero in numeros if 1 <= numero <= total_fontes
            )
        )
        if not validos:
            return '[citação não verificada]'
        return (
            f'({", ".join(f"Fonte {numero}" for numero in validos)}; '
            'citação não verificada)'
        )

    resposta = re.sub(
        r'\(fontes?\s+\d+(?:\s*,\s*\d+)*\)',
        grupo,
        resposta,
        flags=re.I,
    )
    if invalidas:
        resposta += (
            '\n\n> Atenção: uma ou mais citações não correspondem às fontes '
            'recuperadas. Confira a orientação antes de aplicá-la.'
        )
    return resposta
