# ruff: noqa: S101

from types import SimpleNamespace
from unittest import TestCase

from agno.run.agent import RunContentEvent

from chat.agents.contracts import Route, TriageDecision
from chat.agents.orchestrator import IntegraCARAgentWorkflow
from chat.models import Documento
from chat.rag import RetrievedChunk


class FakeAgent:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def run(self, query, *, stream=False, **kwargs):
        self.calls.append({'query': query, 'stream': stream, **kwargs})
        if stream:
            chunks = (
                self.content
                if isinstance(self.content, list)
                else [self.content]
            )
            return iter(RunContentEvent(content=chunk) for chunk in chunks)
        return SimpleNamespace(content=self.content)


class FakeRetriever:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = []

    def __call__(self, query, k, tipos):
        self.calls.append({'query': query, 'k': k, 'tipos': tipos})
        return self.results


def make_agents(decision):
    return {
        'triage': FakeAgent(decision),
        'manual': FakeAgent(['Siga ', 'o procedimento [Fonte 1].']),
        'legal': FakeAgent('Parecer normativo [Fonte 1].'),
        'review': FakeAgent(['Resposta ', 'revisada [Fonte 1].']),
        'general': FakeAgent('Posso ajudar com o CAR.'),
    }


def make_source(document_type=Documento.Tipo.MANUAL):
    return RetrievedChunk(
        conteudo='Trecho documental recuperado.',
        documento_id=1,
        documento_nome='Manual do CAR',
        documento_tipo=document_type,
        score=0.01,
    )


class IntegraCARAgentWorkflowTests(TestCase):
    def test_manual_route_filters_retrieval_and_streams_specialist(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.95,
            rewritten_query='preencher cadastro ambiental rural',
            rationale='Pergunta de procedimento.',
        )
        agents = make_agents(decision)
        retriever = FakeRetriever([make_source()])
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=retriever,
        )

        response = ''.join(workflow.run('Como preencher?', []))

        assert response == 'Siga o procedimento [Fonte 1].'
        assert retriever.calls[0]['tipos'] == (Documento.Tipo.MANUAL,)
        assert '[Fonte 1]' in agents['manual'].calls[0]['query']
        assert not agents['review'].calls

    def test_legal_route_is_reviewed_before_streaming(self):
        decision = TriageDecision(
            route=Route.LEGISLACAO,
            confidence=0.9,
            rewritten_query='legislação reserva legal CAR',
            rationale='Pergunta normativa.',
        )
        agents = make_agents(decision)
        retriever = FakeRetriever([make_source(Documento.Tipo.LEGISLACAO)])
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=retriever,
        )

        response = ''.join(workflow.run('Qual é a norma?', []))

        assert response == 'Resposta revisada [Fonte 1].'
        assert retriever.calls[0]['tipos'] == (Documento.Tipo.LEGISLACAO,)
        assert (
            'Parecer normativo [Fonte 1].'
            in agents['review'].calls[0]['query']
        )

    def test_mixed_route_consults_both_specialists(self):
        decision = TriageDecision(
            route=Route.MISTA,
            confidence=0.88,
            rewritten_query='procedimento e norma para APP',
            rationale='Pergunta mista.',
        )
        agents = make_agents(decision)
        retriever = FakeRetriever([
            make_source(),
            make_source(Documento.Tipo.LEGISLACAO),
        ])
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=retriever,
        )

        response = ''.join(workflow.run('Como cadastrar conforme a lei?', []))

        assert response == 'Resposta revisada [Fonte 1].'
        assert agents['manual'].calls
        assert agents['legal'].calls
        assert retriever.calls[0]['tipos'] == (
            Documento.Tipo.MANUAL,
            Documento.Tipo.LEGISLACAO,
        )

    def test_clarification_stops_before_retrieval(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.7,
            rewritten_query='erro no CAR',
            needs_clarification=True,
            clarification_question='Qual mensagem de erro aparece na tela?',
            rationale='O erro não foi informado.',
        )
        agents = make_agents(decision)
        retriever = FakeRetriever([make_source()])
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=retriever,
        )

        response = ''.join(workflow.run('Deu erro.', []))

        assert response == 'Qual mensagem de erro aparece na tela?'
        assert not retriever.calls

    def test_empty_retrieval_returns_grounded_fallback(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.8,
            rewritten_query='campo desconhecido',
            rationale='Pergunta de procedimento.',
        )
        agents = make_agents(decision)
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=FakeRetriever(),
        )

        response = ''.join(workflow.run('O que preencho aqui?', []))

        assert 'Não encontrei informações suficientes' in response
        assert not agents['manual'].calls
