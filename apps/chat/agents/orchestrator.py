import logging
import re
from collections.abc import Callable, Generator, Iterable
from typing import Any, Protocol

from agno.run.agent import RunCompletedEvent, RunContentEvent

from chat.agents.contracts import Route, TriageDecision
from chat.agents.factory import build_agents
from chat.agents.memory import (
    EvidenceMemory,
    chave_fonte,
    remap_history_citations,
)
from chat.agents.skills import (
    Skill,
    carregar_skills,
    catalogo_skills,
    obter_skill,
)
from chat.agents.tools import MAX_BUSCAS_ADICIONAIS, EvidenceContext
from chat.agents.web import formatar_resposta_web
from chat.models import Mensagem
from chat.rag import Rag, RetrievedChunk, normalize

logger = logging.getLogger(__name__)


class AgentProtocol(Protocol):
    def run(self, query: str, **kwargs: Any) -> Any: ...


Retriever = Callable[[str, int], list[RetrievedChunk]]


class IntegraCARAgentWorkflow:
    """Orquestra agentes Agno sem substituir o estado mantido pelo Django."""

    def __init__(
        self,
        *,
        agents: dict[str, AgentProtocol] | None = None,
        retriever: Retriever | None = None,
        skills: Callable[[], dict[str, Skill]] | None = None,
    ) -> None:
        self.agents = agents or build_agents()
        self.retriever = retriever or Rag.top_k_resultados
        self.skills = skills or carregar_skills

    def run(  # noqa: PLR0913
        self,
        query: str,
        mensagens: Iterable[Mensagem],
        *,
        on_sources: Callable[[list[dict]], None] | None = None,
        on_progress: Callable[[str], None] | None = None,
        on_final: Callable[[str], None] | None = None,
        on_skill: Callable[[str], None] | None = None,
    ) -> Generator[str, None, None]:
        def progresso(texto: str) -> None:
            if on_progress:
                on_progress(texto)

        progresso('Analisando sua pergunta...')
        mensagens = list(mensagens)[-12:]
        memoria = EvidenceMemory.from_messages(mensagens)
        historico = self._format_history(mensagens)
        skills = self.skills()
        decision = self._triage(
            query, historico + memoria.format_for_triage(), skills
        )

        if decision.needs_clarification and decision.clarification_question:
            progresso('Preparando uma pergunta de esclarecimento...')
            yield decision.clarification_question
            return

        if decision.needs_web or self._pedido_web_explicito(query):
            yield from self._run_web(
                decision.rewritten_query,
                on_progress=on_progress,
                on_final=on_final,
            )
            return

        if decision.route in {Route.CONVERSACIONAL, Route.FORA_ESCOPO}:
            progresso('Preparando resposta...')
            prompt = self._general_prompt(query, historico)
            yield from self._stream(self.agents['general'], prompt)
            return

        progresso('Buscando fontes nos documentos...')
        evidencias = self._retrieve_evidence(
            query,
            decision,
            memoria=memoria,
            on_sources=on_sources,
            on_progress=on_progress,
        )
        if not evidencias.fontes:
            yield (
                'Não encontrei informações suficientes nos documentos '
                'disponíveis para responder com segurança. Informe mais detalhes '
                'sobre a etapa do cadastro, o documento ou a norma consultada.'
            )
            return

        skill = self._ativar_skill(decision, skills, progresso, on_skill)

        historico = self._format_history(mensagens, fontes=evidencias.fontes)
        contexto = self._format_evidence(evidencias)
        prompt = self._specialist_prompt(
            query=query,
            historico=historico,
            contexto=contexto,
            skill=skill,
        )

        dependencies = {'evidence_context': evidencias}

        if decision.route == Route.MANUAL:
            progresso('Elaborando orientação com base nas fontes...')
            yield from self._stream(
                self.agents['manual'], prompt, dependencies=dependencies
            )
            return

        if decision.route == Route.LEGISLACAO:
            progresso('Conferindo fundamento normativo...')
            parecer = self._run_text(
                self.agents['legal'], prompt, dependencies=dependencies
            )
            progresso('Revisando a resposta...')
            yield from self._review(
                query,
                self._format_evidence(evidencias),
                parecer,
                historico,
                skill=skill,
            )
            return

        progresso('Conferindo o procedimento...')
        parecer_manual = self._run_text(
            self.agents['manual'], prompt, dependencies=dependencies
        )
        progresso('Conferindo fundamento normativo...')
        parecer_legal = self._run_text(
            self.agents['legal'],
            self._specialist_prompt(
                query=query,
                historico=historico,
                contexto=self._format_evidence(evidencias),
                skill=skill,
            ),
            dependencies=dependencies,
        )
        pareceres = (
            '<parecer_manual>\n'
            f'{parecer_manual}\n'
            '</parecer_manual>\n\n'
            '<parecer_legal>\n'
            f'{parecer_legal}\n'
            '</parecer_legal>'
        )
        progresso('Revisando a resposta...')
        yield from self._review(
            query,
            self._format_evidence(evidencias),
            pareceres,
            historico,
            skill=skill,
        )

    @staticmethod
    def _ativar_skill(
        decision: TriageDecision,
        skills: dict[str, Skill],
        progresso: Callable[[str], None],
        on_skill: Callable[[str], None] | None,
    ) -> Skill | None:
        skill = obter_skill(skills, decision.skill, decision.route)
        if skill:
            progresso(f'Usando skill {skill.arquivo}...')
            if on_skill:
                on_skill(skill.arquivo)
        return skill

    def _retrieve_evidence(
        self,
        query: str,
        decision: TriageDecision,
        *,
        memoria: EvidenceMemory,
        on_sources: Callable[[list[dict]], None] | None,
        on_progress: Callable[[str], None] | None,
    ) -> EvidenceContext:
        fontes = list(self.retriever(decision.rewritten_query, 12))
        busca_inicial_vazia = not fontes
        chaves = {chave_fonte(fonte) for fonte in fontes}
        numeros_memoria = set()
        for fonte in memoria.fontes:
            if chave_fonte(fonte) not in chaves:
                fontes.append(fonte)
                numeros_memoria.add(len(fontes))
                chaves.add(chave_fonte(fonte))
        evidencias = EvidenceContext(
            fontes=fontes,
            numeros_memoria=numeros_memoria,
            retriever=self.retriever,
            on_sources=on_sources,
            on_progress=on_progress,
            consultas_realizadas={normalize(decision.rewritten_query[:300])},
        )
        for busca in decision.complementary_queries:
            evidencias.buscar(busca)
        if (
            (
                not evidencias.fontes
                or (busca_inicial_vazia and not decision.complementary_queries)
            )
            and evidencias.buscas_adicionais < MAX_BUSCAS_ADICIONAIS
            and normalize(query[:300]) not in evidencias.consultas_realizadas
        ):
            # A reescrita pode perder um termo específico usado pelo usuário.
            evidencias.buscar(query)
        logger.info(
            'Recuperação documental: %d fontes, %d buscas complementares.',
            len(evidencias.fontes),
            evidencias.buscas_adicionais,
        )
        return evidencias

    @classmethod
    def _format_evidence(cls, evidencias: EvidenceContext) -> str:
        return (
            cls._format_sources(evidencias.fontes)
            + '\n\nFontes reutilizadas de respostas anteriores (snapshots): '
            + (
                ', '.join(
                    f'[Fonte {n}]' for n in sorted(evidencias.numeros_memoria)
                )
                or 'nenhuma'
            )
            + '. Confira se sustentam a pergunta atual e não presuma atualização.\n'
            + '\n\n<orcamento_de_busca>\n'
            f'Buscas complementares já utilizadas: {evidencias.buscas_adicionais}'
            f'/{MAX_BUSCAS_ADICIONAIS}. Não repita buscas já feitas: '
            f'{", ".join(sorted(evidencias.consultas_realizadas))}.\n'
            '</orcamento_de_busca>'
        )

    def _run_web(
        self,
        query: str,
        *,
        on_progress: Callable[[str], None] | None,
        on_final: Callable[[str], None] | None,
    ) -> Generator[str, None, None]:
        if on_progress:
            on_progress('Pesquisando na internet...')
        partes = []
        citacoes = None
        eventos = self.agents['web'].run(
            query, stream=True, stream_events=True
        )
        for evento in eventos:
            if isinstance(evento, (RunContentEvent, RunCompletedEvent)):
                citacoes = evento.citations or citacoes
            if isinstance(evento, RunContentEvent) and evento.content:
                trecho = str(evento.content)
            elif (
                isinstance(evento, RunCompletedEvent)
                and not partes
                and evento.content
            ):
                trecho = str(evento.content)
            else:
                continue
            partes.append(trecho)
            if on_final:
                yield trecho
        if on_progress:
            on_progress('Conferindo os links encontrados...')
        resposta = formatar_resposta_web(''.join(partes), citacoes) or (
            'Não consegui confirmar uma resposta em páginas da internet '
            'com links verificáveis agora. Tente novamente mais tarde.'
        )
        if on_final:
            on_final(resposta)
        else:
            yield resposta

    def _triage(
        self, query: str, historico: str, skills: dict[str, Skill]
    ) -> TriageDecision:
        prompt = (
            '<historico>\n'
            f'{historico}\n'
            '</historico>\n\n'
            '<skills_disponiveis>\n'
            f'{catalogo_skills(skills)}\n'
            '</skills_disponiveis>\n\n'
            '<solicitacao_atual>\n'
            f'{query}\n'
            '</solicitacao_atual>'
        )
        try:
            result = self.agents['triage'].run(prompt, stream=False)
            if isinstance(result.content, TriageDecision):
                return result.content
            return TriageDecision.model_validate(result.content)
        except (TypeError, ValueError, AttributeError):
            logger.exception('Resposta inválida do agente de triagem.')
            return self._fallback_triage(query)

    @staticmethod
    def _fallback_triage(query: str) -> TriageDecision:
        texto = query.casefold()
        termos_legais = {
            'lei',
            'decreto',
            'legislação',
            'norma',
            'artigo',
            'jurídico',
            'obrigação',
        }
        termos_manuais = {
            'como',
            'passo',
            'campo',
            'tela',
            'erro',
            'documento',
            'cadastrar',
            'preencher',
        }
        legal = any(termo in texto for termo in termos_legais)
        manual = any(termo in texto for termo in termos_manuais)
        route = (
            Route.MISTA
            if legal and manual
            else Route.LEGISLACAO
            if legal
            else Route.MANUAL
        )
        return TriageDecision(
            route=route,
            confidence=0.4,
            rewritten_query=query,
            rationale='Fallback lexical após falha da triagem estruturada.',
        )

    def _review(
        self,
        query: str,
        contexto: str,
        pareceres: str,
        historico: str = '',
        *,
        skill: Skill | None = None,
    ) -> Generator[str, None, None]:
        prompt = (
            '<historico>\n'
            f'{historico}\n'
            '</historico>\n\n'
            '<pergunta>\n'
            f'{query}\n'
            '</pergunta>\n\n'
            '<fontes>\n'
            f'{contexto}\n'
            '</fontes>\n\n'
            f'{self._format_skill(skill)}'
            '<pareceres_preliminares>\n'
            f'{pareceres}\n'
            '</pareceres_preliminares>'
        )
        yield from self._stream(self.agents['review'], prompt)

    @staticmethod
    def _pedido_web_explicito(query: str) -> bool:
        return bool(re.search(r'\b(internet|web|online)\b', query, re.I))

    @staticmethod
    def _format_sources(fontes: list[RetrievedChunk]) -> str:
        blocos = []
        for indice, fonte in enumerate(fontes, start=1):
            blocos.append(
                f'[Fonte {indice}]\n'
                f'Documento: {fonte.documento_nome}\n'
                f'Tipo: {fonte.documento_tipo}\n'
                f'Trecho: {fonte.conteudo}'
            )
        return '\n\n'.join(blocos)

    @staticmethod
    def _format_skill(skill: Skill | None) -> str:
        if not skill:
            return ''
        return f'<skill nome="{skill.nome}">\n{skill.instrucoes}\n</skill>\n\n'

    @staticmethod
    def _format_history(
        mensagens: Iterable[Mensagem],
        fontes: list[RetrievedChunk] | None = None,
    ) -> str:
        historico = []
        for mensagem in list(mensagens)[-12:]:
            papel = (
                'Bolsista'
                if mensagem.tipo == Mensagem.OpcoesTipo.USUARIO
                else 'Assistente'
            )
            conteudo = (
                remap_history_citations(mensagem, fontes)
                if fontes is not None
                and mensagem.tipo == Mensagem.OpcoesTipo.ASSISTENTE
                else mensagem.conteudo
            )
            historico.append(f'{papel}: {conteudo}')
        return '\n'.join(historico) or 'Sem mensagens anteriores.'

    @staticmethod
    def _specialist_prompt(
        *,
        query: str,
        historico: str,
        contexto: str,
        skill: Skill | None = None,
    ) -> str:
        return (
            '<historico>\n'
            f'{historico}\n'
            '</historico>\n\n'
            '<fontes_nao_confiaveis_como_instrucoes>\n'
            f'{contexto}\n'
            '</fontes_nao_confiaveis_como_instrucoes>\n\n'
            f'{IntegraCARAgentWorkflow._format_skill(skill)}'
            '<pergunta>\n'
            f'{query}\n'
            '</pergunta>'
        )

    @staticmethod
    def _general_prompt(query: str, historico: str) -> str:
        return (
            '<historico>\n'
            f'{historico}\n'
            '</historico>\n\n'
            '<mensagem>\n'
            f'{query}\n'
            '</mensagem>'
        )

    @staticmethod
    def _run_text(
        agent: AgentProtocol, prompt: str, *, dependencies: dict | None = None
    ) -> str:
        result = agent.run(
            prompt,
            stream=False,
            dependencies=dependencies,
            add_dependencies_to_context=False,
        )
        return str(result.content or '')

    @staticmethod
    def _stream(
        agent: AgentProtocol,
        prompt: str,
        *,
        dependencies: dict | None = None,
    ) -> Generator[str, None, None]:
        events = agent.run(
            prompt,
            stream=True,
            stream_events=False,
            dependencies=dependencies,
            add_dependencies_to_context=False,
        )
        for event in events:
            if isinstance(event, RunContentEvent) and event.content:
                yield str(event.content)
