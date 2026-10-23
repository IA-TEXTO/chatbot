# ruff: noqa: S101

from importlib import import_module
from types import SimpleNamespace
from unittest import TestCase

from agno.run.agent import RunContentEvent

from chat.agents.contracts import Route, SkillGerada, TriageDecision
from chat.agents.orchestrator import IntegraCARAgentWorkflow
from chat.agents.skills import catalogo_skills, ler_markdown
from chat.models import Documento
from chat.rag import RetrievedChunk
from chat.tasks import markdown_da_skill

SKILL_FLUXO = ler_markdown(
    'fluxo-processos-digitais',
    import_module(
        'chat.migrations.0017_skill_fluxo_processos_digitais'
    ).CONTEUDO,
)


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

    def __call__(self, query, k):
        self.calls.append({'query': query, 'k': k})
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
    def test_manual_route_searches_all_document_types_and_streams_specialist(
        self,
    ):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.95,
            rewritten_query='preencher cadastro ambiental rural',
            rationale='Pergunta de procedimento.',
        )
        agents = make_agents(decision)
        retriever = FakeRetriever([make_source(Documento.Tipo.LEGISLACAO)])
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=retriever,
            skills=dict,
        )

        response = ''.join(workflow.run('Como preencher?', []))

        assert response == 'Siga o procedimento [Fonte 1].'
        assert retriever.calls == [
            {'query': 'preencher cadastro ambiental rural', 'k': 12}
        ]
        assert 'Tipo: legislacao' in agents['manual'].calls[0]['query']
        assert '[Fonte 1]' in agents['manual'].calls[0]['query']
        assert not agents['review'].calls

    def test_sources_callback_preserves_citation_numbers_and_excerpts(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.95,
            rewritten_query='documentos CAR',
            rationale='Pergunta de procedimento.',
        )
        sources = [make_source(), make_source(Documento.Tipo.LEGISLACAO)]
        workflow = IntegraCARAgentWorkflow(
            agents=make_agents(decision),
            retriever=FakeRetriever(sources),
            skills=dict,
        )
        received = []

        ''.join(
            workflow.run('Quais documentos?', [], on_sources=received.extend)
        )

        assert [source['numero'] for source in received] == [1, 2]
        assert received[0]['nome'] == 'Manual do CAR'
        assert received[1]['tipo'] == Documento.Tipo.LEGISLACAO
        assert received[0]['trecho'] == 'Trecho documental recuperado.'

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
            skills=dict,
        )

        response = ''.join(workflow.run('Qual é a norma?', []))

        assert response == 'Resposta revisada [Fonte 1].'
        assert retriever.calls == [
            {'query': 'legislação reserva legal CAR', 'k': 12}
        ]
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
            skills=dict,
        )

        response = ''.join(workflow.run('Como cadastrar conforme a lei?', []))

        assert response == 'Resposta revisada [Fonte 1].'
        assert agents['manual'].calls
        assert agents['legal'].calls
        assert retriever.calls == [
            {'query': 'procedimento e norma para APP', 'k': 12}
        ]

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
            skills=dict,
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
            skills=dict,
        )

        response = ''.join(workflow.run('O que preencho aqui?', []))

        assert 'Não encontrei informações suficientes' in response
        assert not agents['manual'].calls


class SkillTests(TestCase):
    def run_workflow(self, decision):
        agents = make_agents(decision)
        workflow = IntegraCARAgentWorkflow(
            agents=agents,
            retriever=FakeRetriever([make_source()]),
            skills=lambda: {SKILL_FLUXO.nome: SKILL_FLUXO},
        )
        skills, etapas = [], []
        resposta = ''.join(
            workflow.run(
                'O proprietário não respondeu a pendência, o que faço?',
                [],
                on_skill=skills.append,
                on_progress=etapas.append,
            )
        )
        return agents, resposta, skills, etapas

    def test_skill_do_fluxo_criada_pela_migration_e_valida(self):
        assert SKILL_FLUXO.arquivo == 'fluxo-processos-digitais.md'
        assert SKILL_FLUXO.rotas == {Route.MANUAL, Route.MISTA}
        assert '90 dias' in SKILL_FLUXO.instrucoes

    def test_triagem_recebe_catalogo_de_skills_ativas(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.9,
            rewritten_query='documentos CAR',
            rationale='Procedimento.',
        )

        agents, *_ = self.run_workflow(decision)

        prompt = agents['triage'].calls[0]['query']
        assert '<skills_disponiveis>' in prompt
        assert '- fluxo-processos-digitais (rotas: manual, mista)' in prompt
        assert 'Nenhuma skill disponível' in catalogo_skills({})

    def test_skill_escolhida_pela_triagem_guia_o_especialista(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.9,
            rewritten_query='pendência sem resposta do proprietário',
            rationale='Fluxo após a análise.',
            skill='fluxo-processos-digitais',
        )

        agents, _, skills, etapas = self.run_workflow(decision)

        assert skills == ['fluxo-processos-digitais.md']
        assert 'Usando skill fluxo-processos-digitais.md...' in etapas
        prompt = agents['manual'].calls[0]['query']
        assert '<skill nome="fluxo-processos-digitais">' in prompt

    def test_pergunta_sem_skill_segue_fluxo_normal(self):
        decision = TriageDecision(
            route=Route.MANUAL,
            confidence=0.9,
            rewritten_query='documentos CAR',
            rationale='Procedimento.',
        )

        agents, resposta, skills, _ = self.run_workflow(decision)

        assert resposta == 'Siga o procedimento [Fonte 1].'
        assert not skills
        assert '<skill nome=' not in agents['manual'].calls[0]['query']

    def test_skill_inexistente_ou_fora_da_rota_e_ignorada(self):
        for route, skill in (
            (Route.MANUAL, 'skill-inventada'),
            (Route.LEGISLACAO, 'fluxo-processos-digitais'),
        ):
            decision = TriageDecision(
                route=route,
                confidence=0.9,
                rewritten_query='pendência sem resposta',
                rationale='Teste.',
                skill=skill,
            )

            agents, _, skills, _ = self.run_workflow(decision)

            prompts = [
                call['query']
                for agent in agents.values()
                for call in agent.calls
            ]
            assert not skills
            assert not any('<skill nome=' in prompt for prompt in prompts)


class SkillMarkdownTests(TestCase):
    def test_skill_gerada_vira_markdown_valido(self):
        gerada = SkillGerada(
            nome='fluxo-teste',
            titulo='Fluxo de teste',
            documento='Fluxo Oficial (Idaf)',
            descricao='Dúvidas sobre o fluxo de teste.\nNão cobre análise.',
            rotas=[Route.MISTA, Route.MANUAL],
            linha_de_raciocinio='1. Identifique a etapa.',
            referencia='### Etapa 1\n- Prazo de 90 dias.',
            pontos_a_revisar=[],
        )

        skill = ler_markdown('fluxo-teste', markdown_da_skill(gerada))

        assert skill.titulo == 'Fluxo de teste'
        assert skill.descricao == (
            'Dúvidas sobre o fluxo de teste. Não cobre análise.'
        )
        assert skill.rotas == {Route.MANUAL, Route.MISTA}
        assert '## Referência: Fluxo Oficial (Idaf)' in skill.instrucoes
        assert 'Prazo de 90 dias.' in skill.instrucoes

    def test_markdown_invalido_explica_o_problema(self):
        casos = {
            'Sem cabeçalho': 'cabeçalho',
            '---\ntitulo: X\nrotas: manual\n---\nCorpo': 'descricao',
            '---\ntitulo: X\ndescricao: Y\nrotas: conversacional\n---\nC': (
                'Rotas inválidas'
            ),
            '---\ntitulo: X\ndescricao: Y\nrotas: manual\n---\n': (
                'instruções'
            ),
        }
        for conteudo, mensagem in casos.items():
            erro = ''
            try:
                ler_markdown('teste', conteudo)
            except ValueError as excecao:
                erro = str(excecao)
            assert mensagem in erro, conteudo
