# ruff: noqa: S101

from unittest import TestCase

from agno.models.message import Message

from chat.agents.models import IntegraCAROpenAIResponses


class GPT6ToolContinuationTests(TestCase):
    def test_gpt6_continua_ferramenta_usando_resposta_anterior(self):
        model = IntegraCAROpenAIResponses(id='gpt-6-luna', api_key='test')
        messages = [
            Message(role='user', content='Qual é a área?'),
            Message(
                role='assistant',
                tool_calls=[{
                    'id': 'fc_exemplo',
                    'call_id': 'call_exemplo',
                    'type': 'function',
                    'function': {
                        'name': 'consultar_trecho',
                        'arguments': '{"numero": 1}',
                    },
                }],
                provider_data={'response_id': 'resp_exemplo'},
            ),
            Message(
                role='tool',
                content='Trecho do manual.',
                tool_call_id='fc_exemplo',
            ),
        ]

        params = model.get_request_params(messages=messages)
        formatted = model._format_messages(messages)

        assert params['previous_response_id'] == 'resp_exemplo'
        assert params['store'] is True
        assert formatted == [{
            'type': 'function_call_output',
            'call_id': 'call_exemplo',
            'output': 'Trecho do manual.',
        }]

    def test_outros_modelos_mantem_deteccao_original(self):
        assert not IntegraCAROpenAIResponses(
            id='gpt-4.1-nano', api_key='test'
        )._using_reasoning_model()
        assert IntegraCAROpenAIResponses(
            id='gpt-5.6-luna', api_key='test'
        )._using_reasoning_model()
