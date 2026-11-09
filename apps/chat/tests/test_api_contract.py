# ruff: noqa: S101, PLR2004, PT027
"""Valida o contrato HTTP publicado, sem banco ou chamadas ao provedor de IA."""

import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import Client
from ninja.testing import TestClient
from openai import OpenAIError

from chat.api import AI_ERROR_MESSAGE, chat_router


class PublicDocumentationTests(TestCase):
    def test_docs_and_openapi_are_public(self):
        client = Client()
        response = client.get('/api/docs')
        assert response.status_code == 200
        assert b'openapi.json' in response.content

        response = client.get('/api/openapi.json')
        assert response.status_code == 200
        schema = response.json()
        assert schema['info']['title'] == 'API do Chatbot IntegraCAR'
        assert 'Guia de integração' in schema['info']['description']
        chat = schema['paths']['/api/chat']['post']
        content = chat['responses']['200']['content']
        assert 'application/json' in content
        assert 'application/x-ndjson' in content
        assert '400' in chat['responses']
        assert '503' in chat['responses']
        fields = schema['components']['schemas']['RespostaChatSchema']
        assert 'fontes' in fields['required']
        assert 'id_conversa' in fields['required']


class ChatContractTests(TestCase):
    def setUp(self):
        self.client = TestClient(chat_router)

    def post(self, payload):
        return self.client.post('/chat', json=payload, user=AnonymousUser())

    def test_empty_question_returns_documented_400(self):
        response = self.post({'mensagem': '  '})
        assert response.status_code == 400
        assert response.json() == {'resposta': 'Mensagem vazia'}

    def test_missing_question_returns_422(self):
        assert self.post({}).status_code == 422

    def prepare_generation(self):
        # Mantém o roteamento, parsing e serialização reais do Django Ninja.
        self.enter_patch('chat.api.transaction.atomic')
        conversa = self.enter_patch('chat.api.Conversa.objects.create')
        conversa.return_value = SimpleNamespace(id=10)
        mensagens = self.enter_patch('chat.api.Mensagem.objects.create')
        mensagens.side_effect = [
            SimpleNamespace(id=21),
            SimpleNamespace(id=22),
        ]
        self.enter_patch('chat.api._obter_historico').return_value = []
        self.enter_patch('chat.api.Mensagem.objects.filter')
        return self.enter_patch('chat.api.agent_workflow.run')

    def enter_patch(self, target):
        patcher = patch(target)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def test_json_success_preserves_ids_sources_and_skill(self):
        run = self.prepare_generation()
        run.return_value = iter(['Resposta completa'])
        response = self.post({'mensagem': 'Como iniciar?'})
        assert response.status_code == 200
        assert response.json() == {
            'id_conversa': 10,
            'id_mensagem_pergunta': 21,
            'id_mensagem_resposta': 22,
            'resposta': 'Resposta completa',
            'fontes': [],
            'skill': '',
        }

    def test_provider_error_returns_503_instead_of_schema_error(self):
        run = self.prepare_generation()
        run.side_effect = OpenAIError('Provedor indisponível')
        response = self.post({'mensagem': 'Como iniciar?'})
        assert response.status_code == 503
        assert response.json() == {
            'id_conversa': 10,
            'id_mensagem_pergunta': 21,
            'id_mensagem_resposta': 22,
            'resposta': AI_ERROR_MESSAGE,
        }

    def test_stream_is_not_serialized_as_regular_json_response(self):
        run = self.prepare_generation()
        run.return_value = iter(['Resposta completa'])
        response = self.post({'mensagem': 'Como iniciar?', 'stream': True})
        assert response.status_code == 200
        assert response['Content-Type'].startswith('application/x-ndjson')
        events = [json.loads(line) for line in response.content.splitlines()]
        assert events[0] == {
            'id_conversa': 10,
            'id_mensagem_pergunta': 21,
            'id_mensagem_resposta': 22,
        }
        assert events[-2] == {
            'tipo': 'resposta_final',
            'conteudo': 'Resposta completa',
        }
        assert events[-1] == {'tipo': 'fontes', 'fontes': []}
