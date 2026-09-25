# ruff: noqa: S101

from unittest import TestCase

from agno.models.message import Citations, UrlCitation
from agno.run.agent import RunCompletedEvent, RunContentEvent

from chat.agents.contracts import Route, TriageDecision
from chat.agents.orchestrator import IntegraCARAgentWorkflow
from chat.agents.web import formatar_resposta_web
from chat.tests.test_agents import FakeRetriever, make_agents


class WebSearchTests(TestCase):
    def test_citacao_web_aparece_ao_lado_da_afirmacao_com_link(self):
        texto = 'Prazo atualizado.'
        citacoes = Citations(
            raw=[
                {
                    'type': 'url_citation',
                    'start_index': 0,
                    'end_index': len(texto),
                    'url': 'https://www.gov.br/exemplo',
                    'title': 'Página oficial',
                }
            ]
        )

        resposta = formatar_resposta_web(texto, citacoes)

        assert resposta == (
            'Prazo atualizado. [Web 1](<https://www.gov.br/exemplo>)'
        )

    def test_nao_duplica_link_que_o_modelo_ja_citou(self):
        texto = 'Consulte ([Idaf](https://idaf.es.gov.br/car)).'
        citacoes = Citations(raw=[{
            'type': 'url_citation',
            'end_index': len(texto),
            'url': 'https://idaf.es.gov.br/car',
        }])

        assert formatar_resposta_web(texto, citacoes) == texto

    def test_url_insegura_nao_vira_link(self):
        citacoes = Citations(
            raw=[
                {
                    'type': 'url_citation',
                    'end_index': 4,
                    'url': 'javascript:alert(1)',
                }
            ],
            urls=[UrlCitation(url='javascript:alert(1)')],
        )

        assert formatar_resposta_web('Texto', citacoes) is None

    def test_rota_web_pesquisa_sem_consultar_pdfs(self):
        decision = TriageDecision(
            route=Route.LEGISLACAO,
            confidence=0.9,
            rewritten_query='norma CAR vigente ES',
            needs_web=False,
            rationale='Informação atual.',
        )
        agents = make_agents(decision)
        citacoes = Citations(
            raw=[
                {
                    'type': 'url_citation',
                    'end_index': 7,
                    'url': 'https://www.gov.br/exemplo',
                }
            ]
        )
        chamadas = []

        class WebAgent:
            def run(self, query, **kwargs):
                chamadas.append((query, kwargs))
                return iter([
                    RunContentEvent(content='Res'),
                    RunContentEvent(content='posta'),
                    RunCompletedEvent(content='Resposta', citations=citacoes),
                ])

        agents['web'] = WebAgent()
        retriever = FakeRetriever()
        etapas = []
        workflow = IntegraCARAgentWorkflow(agents=agents, retriever=retriever)

        resposta = ''.join(
            workflow.run(
                'Pesquise na internet: qual a norma vigente?',
                [],
                on_progress=etapas.append,
            )
        )

        assert '[Web 1](<https://www.gov.br/exemplo>)' in resposta
        assert chamadas == [
            (
                'norma CAR vigente ES',
                {'stream': True, 'stream_events': True},
            )
        ]
        assert not retriever.calls
        assert 'Pesquisando na internet...' in etapas

    def test_rota_web_transmite_trechos_e_corrige_citacoes_ao_final(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.9,
            rewritten_query='documentos CAR ES',
            needs_web=True,
            rationale='Pesquisa solicitada.',
        )
        agents = make_agents(decision)
        citacoes = Citations(
            raw=[
                {
                    'type': 'url_citation',
                    'end_index': len('Documentos'),
                    'url': 'https://idaf.es.gov.br/car',
                }
            ]
        )

        class WebAgent:
            def run(self, query, **kwargs):
                return iter([
                    RunContentEvent(content='Docu'),
                    RunContentEvent(content='mentos'),
                    RunCompletedEvent(
                        content='Documentos', citations=citacoes
                    ),
                ])

        agents['web'] = WebAgent()
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=FakeRetriever()
        )
        finais = []

        trechos = list(
            workflow.run('Pesquise na internet', [], on_final=finais.append)
        )

        assert trechos == ['Docu', 'mentos']
        assert finais == ['Documentos [Web 1](<https://idaf.es.gov.br/car>)']
