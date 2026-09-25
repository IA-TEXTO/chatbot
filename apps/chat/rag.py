import json
import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from django.conf import settings
from django.db.models import (
    F,
    QuerySet,
    Value,
    Window,
)
from django.db.models.functions import Rank
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.django import CosineDistance

from chat.functions import BM25Score, PdbQueryCast
from chat.models import ChunkDocumeto, Documento, StatusDocumento

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    conteudo: str
    documento_id: int
    documento_nome: str
    documento_tipo: str
    score: float


def normalize(text: str) -> str:
    STOPWORDS = {'a', 'o', 'e', 'de', 'da', 'do', 'para', 'em'}
    text = text.lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    tokens = text.split()
    tokens = [t for t in tokens if t not in STOPWORDS]

    return ' '.join(tokens)


class Rag:
    embedding = OpenAIEmbeddings(
        model='text-embedding-3-small',
        dimensions=1536,
        api_key=settings.OPENAI_API_KEY,
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    @staticmethod
    def extrair_e_salvar_conteudo(id_documento: int) -> None:

        # Usa update() para mudar status sem disparar post_save signal
        updated = Documento.objects.filter(
            id=id_documento,
            status=StatusDocumento.PENDENTE,
        ).update(status=StatusDocumento.PROCESSANDO)

        if not updated:
            logger.warning(
                f'Documento {id_documento} não está PENDENTE '
                f'(possível execução duplicada). Abortando extração.'
            )
            return

        try:
            documento = Documento.objects.get(id=id_documento)

            conteudo = ' '.join([
                d.page_content
                for d in PyPDFLoader(
                    documento.arquivo.path, mode='single'
                ).load()
            ])

            conteudo = re.sub(r'\s+', ' ', conteudo).strip()

            if not conteudo:
                logger.error(
                    f'Documento {id_documento}: conteúdo extraído está vazio.'
                )
                Documento.objects.filter(id=id_documento).update(
                    status=StatusDocumento.ERRO,
                )
                return

            # Usa update() para não disparar o signal post_save
            Documento.objects.filter(id=id_documento).update(
                conteudo=conteudo,
                status=StatusDocumento.PROCESSANDO,
            )
            logger.info(
                f'Documento {id_documento}: conteúdo extraído '
                f'({len(conteudo)} caracteres).'
            )
        except Exception as e:
            logger.exception(
                f'Erro ao extrair conteúdo do documento {id_documento}: {e}'
            )
            Documento.objects.filter(id=id_documento).update(
                status=StatusDocumento.ERRO,
            )
            raise

    # Tamanho máximo de batch para chamadas de embedding (evita timeout)
    EMBEDDING_BATCH_SIZE = 100

    @staticmethod
    def gerar_e_embedar_chunks(id_documento: int) -> None:
        documento = Documento.objects.get(id=id_documento)

        # Verifica se o documento está em estado válido para processamento
        if documento.status not in {
            StatusDocumento.PROCESSANDO,
        }:
            logger.warning(
                f'Documento {id_documento} não está PROCESSANDO '
                f'(status={documento.status}). Abortando geração de chunks.'
            )
            return

        if not documento.conteudo:
            logger.error(
                f'Documento {id_documento} não possui conteúdo. '
                f'Abortando geração de chunks.'
            )
            Documento.objects.filter(id=id_documento).update(
                status=StatusDocumento.ERRO,
            )
            return

        try:
            documento.embeddings.all().delete()

            chunks = Rag.splitter.split_text(documento.conteudo)

            if not chunks:
                logger.error(
                    f'Documento {id_documento}: splitter retornou 0 chunks.'
                )
                Documento.objects.filter(id=id_documento).update(
                    status=StatusDocumento.ERRO,
                )
                return

            logger.info(
                f'Documento {id_documento}: gerando embeddings '
                f'para {len(chunks)} chunks.'
            )

            # Processa embeddings em batches para evitar timeout
            # em documentos grandes
            all_embeddings = []
            for i in range(0, len(chunks), Rag.EMBEDDING_BATCH_SIZE):
                batch = chunks[i : i + Rag.EMBEDDING_BATCH_SIZE]
                batch_embeddings = Rag.embedding.embed_documents(batch)
                all_embeddings.extend(batch_embeddings)

            chunks_documento = [
                ChunkDocumeto(
                    documento=documento,
                    conteudo=chunk,
                    embedding=embedding,
                )
                for chunk, embedding in zip(
                    chunks, all_embeddings, strict=False
                )
            ]

            ChunkDocumeto.objects.bulk_create(chunks_documento)

            # Usa update() para não disparar o signal post_save
            Documento.objects.filter(id=id_documento).update(
                status=StatusDocumento.PROCESSADO,
            )
            logger.info(
                f'Documento {id_documento}: processado com sucesso '
                f'({len(chunks)} chunks criados).'
            )
        except Exception as e:
            logger.exception(
                f'Erro ao gerar chunks do documento {id_documento}: {e}'
            )
            Documento.objects.filter(id=id_documento).update(
                status=StatusDocumento.ERRO,
            )
            raise

    @staticmethod
    def top_k_bm25(query: str, k: int) -> QuerySet[ChunkDocumeto]:
        query_bm25 = json.dumps(
            {'match': {'value': normalize(query)}},
            ensure_ascii=False,
        )
        qs = (
            ChunkDocumeto.objects.filter(
                conteudo__bm25=PdbQueryCast(Value(query_bm25)),
            )
            .annotate(score=BM25Score('id'))
            .order_by('-score')[:k]
        )

        return qs

    @staticmethod
    def top_k_similar(query: str, k: int) -> QuerySet[ChunkDocumeto]:
        embedding_query = Rag.embedding.embed_query(query)

        qs = ChunkDocumeto.objects.annotate(
            score=CosineDistance(
                'embedding',
                embedding_query,
            ),
        ).order_by('score')[:k]

        return qs

    @staticmethod
    def top_k_resultados(
        query: str,
        k: int = 5,
    ) -> list[RetrievedChunk]:
        embedding_query = Rag.embedding.embed_query(query)

        filtros = {'documento__status': StatusDocumento.PROCESSADO}

        query_bm25 = json.dumps(
            {'match': {'value': normalize(query)}},
            ensure_ascii=False,
        )

        ranked_by_bm25 = (
            ChunkDocumeto.objects.filter(**filtros)
            .select_related('documento')
            .annotate(
                score=BM25Score('id'),
                rank=Window(expression=Rank(), order_by=F('score').desc()),
            )
            .filter(conteudo__bm25=PdbQueryCast(Value(query_bm25)))
            .order_by('-score')
        )

        ranked_by_semantic = (
            ChunkDocumeto.objects.filter(**filtros)
            .select_related('documento')
            .annotate(
                score=CosineDistance('embedding', embedding_query),
                rank=Window(expression=Rank(), order_by=F('score').asc()),
            )
            .order_by('score')
        )

        combinado = Rag._combine_rankings(
            ranked_by_bm25[: k * 4],
            ranked_by_semantic[: k * 4],
        )
        return [
            RetrievedChunk(
                conteudo=chunk.conteudo,
                documento_id=chunk.documento_id,
                documento_nome=chunk.documento.nome,
                documento_tipo=chunk.documento.tipo,
                score=chunk.score,
            )
            for chunk in combinado[:k]
        ]

    @staticmethod
    def _combine_rankings(
        ranked_by_bm25: Iterable[ChunkDocumeto],
        ranked_by_semantic: Iterable[ChunkDocumeto],
    ) -> list[ChunkDocumeto]:
        agrupado = defaultdict(list)
        for chunk in ranked_by_bm25:
            agrupado[chunk.id].append(('bm25', chunk))
        for chunk in ranked_by_semantic:
            agrupado[chunk.id].append(('semantic', chunk))

        combinado = []
        rrf_constant = 60

        for chunks in agrupado.values():
            rank_bm25 = next((c.rank for t, c in chunks if t == 'bm25'), None)
            rank_sem = next(
                (c.rank for t, c in chunks if t == 'semantic'), None
            )

            score_bm25 = 1.0 / (rrf_constant + rank_bm25) if rank_bm25 else 0.0
            score_sem = 1.0 / (rrf_constant + rank_sem) if rank_sem else 0.0
            total_score = (0.5 * score_bm25) + (0.5 * score_sem)

            representante = chunks[0][1]
            representante.score = total_score
            combinado.append(representante)

        combinado.sort(key=lambda x: x.score, reverse=True)
        return combinado

    @staticmethod
    def top_k_chunks(
        query: str,
        k: int = 5,
    ) -> list[str]:
        return [
            resultado.conteudo
            for resultado in Rag.top_k_resultados(query, k=k)
        ]
