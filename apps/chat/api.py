import json

from agno.exceptions import AgnoError
from django.db import transaction
from django.http import FileResponse, HttpRequest, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django_cte import CTE, with_cte
from ninja import Router
from ninja.errors import HttpError
from openai import OpenAIError

from chat.agents import IntegraCARAgentWorkflow
from chat.models import Conversa, Documento, Mensagem
from chat.schemas import (
    AtualizarTipoDocumentoSchema,
    ChatSchema,
    CurtirMensagemSchema,
)

chat_router = Router()
agent_workflow = IntegraCARAgentWorkflow()
AI_ERRORS = (AgnoError, OpenAIError)
AI_ERROR_MESSAGE = (
    'Não foi possível gerar a resposta agora. Tente novamente em instantes.'
)


def _obter_mensagem_pai(
    conversa: Conversa,
    payload: ChatSchema,
) -> Mensagem | None:
    id_mensagem_pai = payload.id_mensagem_pai
    if payload.id_mensagem_editada is not None:
        mensagem_editada = get_object_or_404(
            Mensagem.objects.only('id', 'mensagem_pai_id'),
            id=payload.id_mensagem_editada,
            conversa_id=conversa.id,
            tipo=Mensagem.OpcoesTipo.USUARIO,
        )
        id_mensagem_pai = mensagem_editada.mensagem_pai_id

    if id_mensagem_pai is None:
        return None

    return get_object_or_404(
        Mensagem.objects.only('id'),
        id=id_mensagem_pai,
        conversa_id=conversa.id,
        tipo=Mensagem.OpcoesTipo.ASSISTENTE,
    )


def _obter_historico(
    conversa_id: int,
    id_mensagem_pai: int | None,
):
    def mensagens_cte(cte: CTE):
        values = ('id', 'mensagem_pai_id', 'conteudo', 'criado_em')
        return (
            Mensagem.objects.filter(
                conversa_id=conversa_id,
                id=id_mensagem_pai,
            )
            .values(*values)
            .union(
                cte.join(Mensagem, id=cte.col.mensagem_pai_id).values(*values),
                all=True,
            )
        )

    cte = CTE.recursive(mensagens_cte)
    return with_cte(
        cte,
        select=cte.join(Mensagem, id=cte.col.id).order_by('criado_em'),
    )


@chat_router.post('/chat')
def chat_endpoint(request: HttpRequest, payload: ChatSchema):
    mensagem = payload.mensagem.strip()
    stream = payload.stream

    if not mensagem:
        return 400, {'resposta': 'Mensagem vazia'}

    # Criar objetos no banco de forma atômica
    with transaction.atomic():
        if payload.id_conversa:
            conversa = Conversa.objects.select_for_update().get(
                id=payload.id_conversa,
                usuario=request.user
                if request.user.is_authenticated
                else None,
            )
        else:
            tamanho_maximo = 20
            conversa = Conversa.objects.create(
                usuario=request.user
                if request.user.is_authenticated
                else None,
                nome=mensagem[:tamanho_maximo] + '...'
                if len(mensagem) > tamanho_maximo
                else mensagem,
            )

        mensagem_pai = _obter_mensagem_pai(conversa, payload)

        mensagem_pergunta = Mensagem.objects.create(
            conversa_id=conversa.id,
            conteudo=mensagem,
            mensagem_pai=mensagem_pai,
            tipo=Mensagem.OpcoesTipo.USUARIO,
        )

        mensagem_resposta = Mensagem.objects.create(
            conversa_id=conversa.id,
            mensagem_pai_id=mensagem_pergunta.id,
            tipo=Mensagem.OpcoesTipo.ASSISTENTE,
            conteudo='',
        )

    mensagens = _obter_historico(
        conversa.id,
        mensagem_pai.id if mensagem_pai else None,
    )

    base_response = {
        'id_conversa': conversa.id,
        'id_mensagem_pergunta': mensagem_pergunta.id,
        'id_mensagem_resposta': mensagem_resposta.id,
    }

    fontes = []

    def registrar_fontes(fontes_recuperadas):
        fontes[:] = fontes_recuperadas

    resposta = agent_workflow.run(
        mensagem, mensagens, on_sources=registrar_fontes
    )

    if not stream:
        try:
            resposta_completa = ''.join(resposta)
        except AI_ERRORS:
            Mensagem.objects.filter(id=mensagem_resposta.id).update(
                conteudo=AI_ERROR_MESSAGE, fontes=[]
            )
            return 503, base_response | {'resposta': AI_ERROR_MESSAGE}
        Mensagem.objects.filter(id=mensagem_resposta.id).update(
            conteudo=resposta_completa, fontes=fontes
        )
        return 200, base_response | {
            'resposta': resposta_completa, 'fontes': fontes
        }

    def resposta_streaming():
        yield json.dumps(base_response) + '\n'
        chunks = []
        try:
            for chunk_resposta in resposta:
                chunks.append(chunk_resposta)
                yield json.dumps(
                    {'tipo': 'trecho', 'conteudo': chunk_resposta}
                ) + '\n'
        except AI_ERRORS:
            chunk_resposta = f'\n\n{AI_ERROR_MESSAGE}'
            fontes.clear()
            chunks.append(chunk_resposta)
            yield json.dumps(
                {'tipo': 'trecho', 'conteudo': chunk_resposta}
            ) + '\n'

        Mensagem.objects.filter(id=mensagem_resposta.id).update(
            conteudo=''.join(chunks), fontes=fontes
        )
        yield json.dumps({'tipo': 'fontes', 'fontes': fontes}) + '\n'

    return StreamingHttpResponse(
        resposta_streaming(),
        content_type='application/x-ndjson; charset=utf-8',
    )


@chat_router.get('/documentos/{id_documento}/status')
def status_documento(request: HttpRequest, id_documento: int):
    documento = get_object_or_404(Documento, id=id_documento)
    return {'status': documento.status}


@chat_router.patch('/documentos/{id_documento}/tipo')
def atualizar_tipo_documento(
    request: HttpRequest,
    id_documento: int,
    payload: AtualizarTipoDocumentoSchema,
):
    documento = get_object_or_404(Documento, id=id_documento)
    tipo = payload.tipo

    documento.tipo = tipo
    documento.save(update_fields=['tipo'])

    return 400, {'error': 'Tipo inválido'}


@chat_router.patch('/mensagens/{id_mensagem}/curtir')
def curtir_mensagem(
    request: HttpRequest,
    id_mensagem: int,
    payload: CurtirMensagemSchema,
):
    mensagem = get_object_or_404(Mensagem, id=id_mensagem)
    mensagem.curtido = payload.curtido
    mensagem.save(update_fields=['curtido'])
    return {'curtido': mensagem.curtido}


@chat_router.get('/mensagens/{id_mensagem}/documentos/{id_documento}/arquivo')
def arquivo_fonte(request: HttpRequest, id_mensagem: int, id_documento: int):
    if not request.user.is_authenticated:
        raise HttpError(403, 'Entre na sua conta para abrir o PDF.')

    mensagem = get_object_or_404(
        Mensagem, id=id_mensagem, tipo=Mensagem.OpcoesTipo.ASSISTENTE,
        conversa__usuario=request.user,
    )
    documentos_citados = [
        fonte.get('documento_id') for fonte in mensagem.fontes
    ]
    documento = get_object_or_404(
        Documento, id=id_documento, id__in=documentos_citados
    )
    return FileResponse(
        documento.arquivo.open('rb'),
        content_type='application/pdf',
        filename=documento.arquivo.name.rsplit('/', 1)[-1],
    )
