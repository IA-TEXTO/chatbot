from agno.agent import Agent
from django.conf import settings

from chat.agents.contracts import SkillGerada, TriageDecision
from chat.agents.models import IntegraCAROpenAIResponses
from chat.agents.prompts import (
    GENERAL_INSTRUCTIONS,
    LEGAL_INSTRUCTIONS,
    MANUAL_INSTRUCTIONS,
    REVIEW_INSTRUCTIONS,
    SKILL_WRITER_INSTRUCTIONS,
    TRIAGE_INSTRUCTIONS,
    WEB_INSTRUCTIONS,
)
from chat.agents.tools import (
    buscar_fontes,
    consultar_resposta_canonica,
    consultar_trecho,
    registrar_chamada_ferramenta,
)


def _model(*, timeout: int = 60, max_retries: int = 2):
    return IntegraCAROpenAIResponses(
        id=settings.INTEGRACAR_CHAT_MODEL,
        api_key=settings.OPENAI_API_KEY,
        timeout=timeout,
        max_retries=max_retries,
    )


def build_agents() -> dict[str, Agent]:
    common = {
        'markdown': True,
        'telemetry': False,
        'retries': 1,
    }
    return {
        'triage': Agent(
            id='integracar-triage',
            name='Triagem IntegraCAR',
            model=_model(),
            instructions=TRIAGE_INSTRUCTIONS,
            output_schema=TriageDecision,
            structured_outputs=True,
            telemetry=False,
            retries=1,
        ),
        'manual': Agent(
            id='integracar-manual',
            name='Especialista em procedimentos do CAR',
            model=_model(),
            instructions=MANUAL_INSTRUCTIONS,
            tools=[
                buscar_fontes,
                consultar_trecho,
                consultar_resposta_canonica,
            ],
            tool_call_limit=4,
            tool_hooks=[registrar_chamada_ferramenta],
            **common,
        ),
        'legal': Agent(
            id='integracar-legislation',
            name='Especialista em legislação ambiental',
            model=_model(),
            instructions=LEGAL_INSTRUCTIONS,
            tools=[
                buscar_fontes,
                consultar_trecho,
                consultar_resposta_canonica,
            ],
            tool_call_limit=4,
            tool_hooks=[registrar_chamada_ferramenta],
            **common,
        ),
        'review': Agent(
            id='integracar-evidence-review',
            name='Revisor de evidências',
            model=_model(),
            instructions=REVIEW_INSTRUCTIONS,
            **common,
        ),
        'web': Agent(
            id='integracar-web',
            name='Pesquisa web do IntegraCAR',
            model=_model(),
            instructions=WEB_INSTRUCTIONS,
            tools=[{'type': 'web_search', 'search_context_size': 'medium'}],
            tool_choice='required',
            **common,
        ),
        'general': Agent(
            id='integracar-general',
            name='Assistente IntegraCAR',
            model=_model(),
            instructions=GENERAL_INSTRUCTIONS,
            **common,
        ),
    }


def build_skill_writer() -> Agent:
    return Agent(
        id='integracar-skill-writer',
        name='Redator de skills do IntegraCAR',
        # Abaixo do timeout de 100s do django-q para não deixar a skill
        # presa em "gerando".
        model=_model(timeout=90, max_retries=0),
        instructions=SKILL_WRITER_INSTRUCTIONS,
        output_schema=SkillGerada,
        structured_outputs=True,
        telemetry=False,
    )
