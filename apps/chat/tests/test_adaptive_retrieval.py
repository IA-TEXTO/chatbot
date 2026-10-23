# ruff: noqa: S101, PLR2004, PT027
"""Cenários controlados de recuperação; não medem qualidade do modelo real."""

from unittest import TestCase

from pydantic import ValidationError

from chat.agents.contracts import Route, TriageDecision
from chat.agents.orchestrator import IntegraCARAgentWorkflow
from chat.agents.tools import MAX_FONTES, EvidenceContext
from chat.tests.test_agent_tools import fonte
from chat.tests.test_agents import make_agents


class ScenarioRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, query, k):
        self.calls.append((query, k))
        return self.results.get(query, [])


def decision(**kwargs):
    return TriageDecision(
        route=Route.MANUAL,
        confidence=0.9,
        rewritten_query='preenchimento CAR',
        rationale='Consulta documental.',
        **kwargs,
    )


class AdaptiveRetrievalTests(TestCase):
    def test_recovers_evidence_before_abstaining(self):
        retriever = ScenarioRetriever({
            'documentos necessários CAR': [fonte('Lista documental')],
        })
        agents = make_agents(
            decision(
                complementary_queries=['documentos necessários CAR'],
            )
        )
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=retriever, skills=dict
        )
        publicadas = []
        etapas = []

        resposta = ''.join(
            workflow.run(
                'Quais documentos preciso?',
                [],
                on_sources=publicadas.append,
                on_progress=etapas.append,
            )
        )

        assert 'Não encontrei' not in resposta
        assert 'Lista documental' in agents['manual'].calls[0]['query']
        assert publicadas[-1][0]['numero'] == 1
        assert retriever.calls == [
            ('preenchimento CAR', 12),
            ('documentos necessários CAR', 6),
        ]
        assert 'Fazendo uma busca complementar nos documentos...' in etapas

    def test_original_question_can_recover_a_term_lost_in_rewrite(self):
        query = 'Como corrigir erro GEO-123 no CAR?'
        retriever = ScenarioRetriever({query: [fonte('Orientação GEO-123')]})
        agents = make_agents(decision())
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=retriever, skills=dict
        )

        ''.join(workflow.run(query, []))

        assert retriever.calls == [('preenchimento CAR', 12), (query, 6)]
        assert 'Orientação GEO-123' in agents['manual'].calls[0]['query']

    def test_multitopic_question_keeps_both_aspects_and_stable_citations(self):
        triage = decision(complementary_queries=['documentos CAR'])
        triage.route = Route.MISTA
        inicial = fonte('Passos para APP')
        retriever = ScenarioRetriever({
            'preenchimento CAR': [inicial],
            'documentos CAR': [inicial, fonte('Documentação exigida', 2)],
        })
        agents = make_agents(triage)
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=retriever, skills=dict
        )
        fontes = []

        ''.join(
            workflow.run(
                'Como declarar APP e quais documentos?',
                [],
                on_sources=fontes.append,
            )
        )

        assert [item['numero'] for item in fontes[-1]] == [1, 2]
        for name in ['manual', 'legal', 'review']:
            prompt = agents[name].calls[0]['query']
            assert 'Passos para APP' in prompt
            assert 'Documentação exigida' in prompt
        assert 'já utilizadas: 1/2' in agents['legal'].calls[0]['query']

    def test_no_evidence_after_budget_still_abstains(self):
        retriever = ScenarioRetriever({})
        agents = make_agents(
            decision(complementary_queries=['APP CAR', 'reserva legal CAR'])
        )
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=retriever, skills=dict
        )

        resposta = ''.join(workflow.run('Pergunta original', []))

        assert 'Não encontrei informações suficientes' in resposta
        assert len(retriever.calls) == 3
        assert not agents['manual'].calls
        assert not agents['legal'].calls

    def test_simple_question_keeps_single_search(self):
        retriever = ScenarioRetriever({'preenchimento CAR': [fonte('Trecho')]})
        workflow = IntegraCARAgentWorkflow(
            agents=make_agents(decision()),
            retriever=retriever,
            skills=dict,
        )
        ''.join(workflow.run('Como preencher?', []))
        assert retriever.calls == [('preenchimento CAR', 12)]

    def test_duplicate_queries_do_not_spend_budget(self):
        retriever = ScenarioRetriever({})
        contexto = EvidenceContext(fontes=[], retriever=retriever)
        contexto.buscar('Documentação CAR')
        repetida = contexto.buscar('  documentacao car  ')
        contexto.buscar('APP CAR')
        excedente = contexto.buscar('Outra consulta')
        assert 'já foi realizada' in repetida['erro']
        assert 'Limite' in excedente['erro']
        assert len(retriever.calls) == 2

    def test_planner_and_specialist_share_budget(self):
        retriever = ScenarioRetriever({'preenchimento CAR': [fonte('Trecho')]})
        agents = make_agents(
            decision(complementary_queries=['APP CAR', 'documentos CAR'])
        )
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=retriever, skills=dict
        )
        ''.join(workflow.run('Como preencher?', []))
        contexto = agents['manual'].calls[0]['dependencies'][
            'evidence_context'
        ]
        assert 'Limite' in contexto.buscar('terceira busca')['erro']
        assert len(retriever.calls) == 3

    def test_source_cap_avoids_unnecessary_retrieval(self):
        retriever = ScenarioRetriever({})
        contexto = EvidenceContext(
            fontes=[fonte(f'Trecho {i}') for i in range(MAX_FONTES)],
            retriever=retriever,
        )
        assert 'Limite de fontes' in contexto.buscar('APP CAR')['erro']
        assert not retriever.calls

    def test_search_plan_validation_and_backwards_compatibility(self):
        assert decision().complementary_queries == []
        assert decision(
            complementary_queries=['  APP CAR  ', ' ']
        ).complementary_queries == ['APP CAR']
        with self.assertRaises(ValidationError):
            decision(complementary_queries=['a', 'b', 'c'])
        dados = decision().model_dump()
        dados['rewritten_query'] = '   '
        with self.assertRaises(ValidationError):
            TriageDecision.model_validate(dados)

    def test_clarification_never_executes_planned_searches(self):
        retriever = ScenarioRetriever({})
        agents = make_agents(
            decision(
                complementary_queries=['documentos CAR'],
                needs_clarification=True,
                clarification_question='Em qual etapa aparece o erro?',
            )
        )
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=retriever, skills=dict
        )
        resposta = ''.join(workflow.run('Deu erro', []))
        assert resposta == 'Em qual etapa aparece o erro?'
        assert not retriever.calls
