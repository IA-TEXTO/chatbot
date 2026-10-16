# ruff: noqa: S101, PLR2004
from types import SimpleNamespace
from unittest import TestCase

from chat.agents.memory import (
    MAX_CARACTERES_MEMORIA,
    EvidenceMemory,
    remap_history_citations,
)
from chat.agents.orchestrator import IntegraCARAgentWorkflow
from chat.tests.test_adaptive_retrieval import ScenarioRetriever, decision
from chat.tests.test_agent_tools import fonte
from chat.tests.test_agents import make_agents


def snapshot(texto='Exceção para APP', numero=2, documento=7):
    return {
        'numero': numero,
        'documento_id': documento,
        'nome': 'Manual.pdf',
        'tipo': 'manual',
        'trecho': texto,
    }


def mensagem(conteudo='Confira [Fonte 2].', fontes=None, tipo='ASSISTENTE'):
    return SimpleNamespace(tipo=tipo, conteudo=conteudo, fontes=fontes or [])


class EvidenceMemoryTests(TestCase):
    def test_followup_receives_old_chunks_with_new_citation_numbers(self):
        agents = make_agents(decision())
        retriever = ScenarioRetriever({
            'preenchimento CAR': [fonte('Trecho atual')]
        })
        workflow = IntegraCARAgentWorkflow(agents=agents, retriever=retriever)
        fontes = []
        historico = [
            mensagem(
                fontes=[snapshot(numero=9)], conteudo='Exceção [Fonte 9].'
            )
        ]
        ''.join(
            workflow.run(
                'Essa exceção vale neste caso?',
                iter(historico),
                on_sources=fontes.append,
            )
        )
        assert 'Exceção para APP' in agents['triage'].calls[0]['query']
        prompt = agents['manual'].calls[0]['query']
        assert 'Assistente: Exceção [Fonte 2].' in prompt
        assert 'Trecho: Exceção para APP' in prompt
        assert 'snapshots): [Fonte 2]' in prompt
        assert fontes[-1][1]['documento_id'] == 7
        contexto = agents['manual'].calls[0]['dependencies'][
            'evidence_context'
        ]
        assert contexto.trecho(2)['trecho'] == 'Exceção para APP'

    def test_old_evidence_is_available_when_search_does_not_find_it_again(
        self,
    ):
        agents = make_agents(decision())
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=ScenarioRetriever({})
        )
        resposta = ''.join(
            workflow.run('E essa exceção?', [mensagem(fontes=[snapshot()])])
        )
        assert 'Não encontrei' not in resposta
        assert 'Trecho: Exceção para APP' in agents['manual'].calls[0]['query']

    def test_fresh_and_old_duplicate_is_published_once(self):
        agents = make_agents(decision())
        retriever = ScenarioRetriever({
            'preenchimento CAR': [fonte('Mesmo trecho', 7)]
        })
        workflow = IntegraCARAgentWorkflow(agents=agents, retriever=retriever)
        fontes = []
        ''.join(
            workflow.run(
                'Explique',
                [mensagem(fontes=[snapshot('Mesmo trecho')])],
                on_sources=fontes.append,
            )
        )
        assert len(fontes[-1]) == 1
        assert (
            'Assistente: Confira [Fonte 1].'
            in agents['manual'].calls[0]['query']
        )

    def test_unavailable_reference_cannot_alias_a_fresh_source(self):
        antiga = mensagem(
            fontes=[snapshot()],
            conteudo='Um [Fonte 1], outro [Fonte 2]. (fontes 1, 2)',
        )
        texto = remap_history_citations(antiga, [fonte('Outro trecho')])
        assert '[Fonte 1]' not in texto
        assert '[Fonte 2]' not in texto
        assert 'fora do contexto atual' in texto

    def test_recent_cited_sources_have_priority_and_memory_is_bounded(self):
        fontes = [snapshot(f'Trecho {n}', n) for n in range(1, 8)]
        memoria = EvidenceMemory.from_messages([
            mensagem(fontes=[snapshot('Mais antiga', 1)]),
            mensagem('Confira [Fonte 7]', fontes),
        ])
        assert len(memoria.fontes) == 4
        assert memoria.fontes[0].conteudo == 'Trecho 7'
        assert 'Mais antiga' not in [f.conteudo for f in memoria.fontes]
        memoria = EvidenceMemory.from_messages([
            mensagem(
                fontes=[
                    snapshot('x' * (MAX_CARACTERES_MEMORIA + 1)),
                    snapshot('Curto', 3),
                ]
            )
        ])
        assert [f.conteudo for f in memoria.fontes] == ['Curto']

    def test_duplicate_old_chunks_do_not_consume_memory(self):
        antiga = mensagem(fontes=[snapshot()])
        memoria = EvidenceMemory.from_messages([antiga, antiga])
        assert len(memoria.fontes) == 1

    def test_legacy_or_malformed_sources_are_ignored(self):
        fontes = [
            None,
            'texto',
            {},
            snapshot(''),
            dict(snapshot(), numero=[]),
            dict(snapshot(), documento_id=True),
        ]
        memoria = EvidenceMemory.from_messages([
            mensagem(fontes=fontes),
            mensagem(fontes='inválido'),
            SimpleNamespace(tipo='ASSISTENTE', conteudo='Sem fontes'),
            mensagem(fontes=[snapshot()], tipo='USUARIO'),
        ])
        assert not memoria.fontes

    def test_memory_only_uses_received_branch_and_recent_window(self):
        ramo_a = mensagem(fontes=[snapshot('Ramo A')])
        ramo_b = mensagem(fontes=[snapshot('Ramo B')])
        assert (
            EvidenceMemory.from_messages([ramo_a]).fontes[0].conteudo
            == 'Ramo A'
        )
        assert (
            EvidenceMemory.from_messages([ramo_b]).fontes[0].conteudo
            == 'Ramo B'
        )
        assert not EvidenceMemory.from_messages(
            [ramo_a] + [mensagem() for _ in range(12)]
        ).fontes

    def test_legal_reviewer_receives_remapped_history_and_old_evidence(self):
        triage = decision()
        triage.route = 'legislacao'
        agents = make_agents(triage)
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=ScenarioRetriever({})
        )
        ''.join(
            workflow.run(
                'Essa exceção se aplica?', [mensagem(fontes=[snapshot()])]
            )
        )
        prompt = agents['review'].calls[0]['query']
        assert 'Assistente: Confira [Fonte 1].' in prompt
        assert 'Trecho: Exceção para APP' in prompt

    def test_source_snapshots_are_not_modified(self):
        dados = snapshot()
        antiga = mensagem(fontes=[dados])
        EvidenceMemory.from_messages([antiga])
        remap_history_citations(antiga, [fonte('Outro')])
        assert dados == snapshot()
        assert antiga.conteudo == 'Confira [Fonte 2].'

    def test_no_memory_leaks_between_runs_of_same_workflow(self):
        agents = make_agents(decision())
        workflow = IntegraCARAgentWorkflow(
            agents=agents, retriever=ScenarioRetriever({})
        )
        ''.join(
            workflow.run('E essa exceção?', [mensagem(fontes=[snapshot()])])
        )
        assert 'Exceção para APP' in agents['manual'].calls[0]['query']
        resposta = ''.join(workflow.run('Outra consulta', []))
        assert 'Não encontrei informações suficientes' in resposta
        assert len(agents['manual'].calls) == 1

    def test_grouped_citations_are_remapped_individually(self):
        antiga = mensagem(
            conteudo='Confira (fontes 1, 2).',
            fontes=[snapshot(numero=1), snapshot('Outro', 2)],
        )
        texto = remap_history_citations(
            antiga, [fonte('Outro', 7), fonte('Exceção para APP', 7)]
        )
        assert texto == 'Confira ([Fonte 2], [Fonte 1]).'
