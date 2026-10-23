import logging

from django.utils.text import slugify
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import TokenTextSplitter

from chat.agents.contracts import SkillGerada
from chat.agents.factory import build_skill_writer
from chat.agents.skills import ler_markdown, montar_markdown
from chat.models import ChunkDocumeto, Documento, Skill, StatusDocumento
from chat.rag import Rag

logger = logging.getLogger(__name__)


def gerar_embedding_documento(documento_id: int):
    """Task legada - mantida por compatibilidade.
    Prefira usar a chain via signal (extrair_e_salvar_conteudo + gerar_e_embedar_chunks).
    """
    # Usa update() para não disparar o signal post_save
    updated = Documento.objects.filter(
        id=documento_id,
        status=StatusDocumento.PENDENTE,
    ).update(status=StatusDocumento.PROCESSANDO)

    if not updated:
        logger.warning(
            f'Documento {documento_id} não está PENDENTE. '
            f'Abortando (possível execução duplicada).'
        )
        return

    try:
        documento = Documento.objects.get(id=documento_id)

        text_splitter = TokenTextSplitter(
            chunk_size=512,
            chunk_overlap=256,
        )

        conteudo = PyPDFLoader(documento.arquivo.path, mode='single').load()

        chunks = text_splitter.split_documents(conteudo)
        chunks = [chunk.page_content.replace('\n', '') for chunk in chunks]

        if not chunks:
            logger.error(f'Documento {documento_id}: nenhum chunk gerado.')
            Documento.objects.filter(id=documento_id).update(
                status=StatusDocumento.ERRO,
            )
            return

        embeddings = Rag.embedding.embed_documents(chunks)

        embeddings = [
            ChunkDocumeto(
                documento=documento,
                conteudo=chunk,
                embedding=embedding,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=False)
        ]

        documento.embeddings.all().delete()

        ChunkDocumeto.objects.bulk_create(embeddings)

        # Usa update() para não disparar o signal post_save
        Documento.objects.filter(id=documento_id).update(
            status=StatusDocumento.PROCESSADO,
        )
        logger.info(f'Documento {documento_id}: processado com sucesso.')
    except Exception as e:
        logger.exception(f'Erro ao processar documento {documento_id}: {e}')
        Documento.objects.filter(id=documento_id).update(
            status=StatusDocumento.ERRO,
        )
        raise


MAX_CARACTERES_SKILL = 40_000


def nome_skill_disponivel(base: str, *, ignorar_id: int | None = None) -> str:
    base = slugify(base)[:80] or 'skill'
    nome, sufixo = base, 2
    existentes = Skill.objects.exclude(id=ignorar_id)
    while existentes.filter(nome=nome).exists():
        nome, sufixo = f'{base}-{sufixo}', sufixo + 1
    return nome


def markdown_da_skill(gerada: SkillGerada) -> str:
    instrucoes = (
        '## Linha de raciocínio\n\n'
        f'{gerada.linha_de_raciocinio.strip()}\n\n'
        f'## Referência: {gerada.documento.strip()}\n\n'
        f'{gerada.referencia.strip()}'
    )
    return montar_markdown(
        titulo=gerada.titulo,
        descricao=gerada.descricao,
        rotas=gerada.rotas,
        instrucoes=instrucoes,
    )


def gerar_skill_de_pdf(id_skill: int):
    """Gera um rascunho de skill a partir do PDF; a ativação é manual."""
    skill = Skill.objects.get(id=id_skill, status=Skill.Status.GERANDO)
    try:
        paginas = PyPDFLoader(skill.arquivo_origem.path, mode='single').load()
        texto = ''.join(pagina.page_content for pagina in paginas).strip()
        if not texto:
            raise ValueError('O PDF não tem texto extraível.')

        resultado = build_skill_writer().run(
            f'<documento>\n{texto[:MAX_CARACTERES_SKILL]}\n</documento>',
            stream=False,
        )
        gerada = SkillGerada.model_validate(resultado.content)
        nome = nome_skill_disponivel(gerada.nome, ignorar_id=skill.id)
        conteudo = markdown_da_skill(gerada)
        ler_markdown(nome, conteudo)
    except Exception as erro:
        logger.exception(f'Erro ao gerar a skill {id_skill}: {erro}')
        Skill.objects.filter(id=id_skill).update(
            status=Skill.Status.ERRO,
            observacoes=(
                f'Não foi possível gerar a skill: {erro}'
                if isinstance(erro, ValueError)
                else 'Não foi possível gerar a skill. Tente enviar o PDF '
                'novamente.'
            ),
        )
        return

    Skill.objects.filter(id=id_skill).update(
        nome=nome,
        conteudo=conteudo,
        observacoes='\n'.join(gerada.pontos_a_revisar),
        status=Skill.Status.RASCUNHO,
    )
    logger.info(f'Skill {id_skill}: rascunho gerado.')
