from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from django.conf import settings

from chat.agents.contracts import TriageDecision
from chat.agents.prompts import (
    GENERAL_INSTRUCTIONS,
    LEGAL_INSTRUCTIONS,
    MANUAL_INSTRUCTIONS,
    REVIEW_INSTRUCTIONS,
    TRIAGE_INSTRUCTIONS,
    WEB_INSTRUCTIONS,
)
from chat.agents.tools import (
    buscar_fontes,
    consultar_resposta_canonica,
    consultar_trecho,
    registrar_chamada_ferramenta,
)


def _model() -> OpenAIResponses:
    return OpenAIResponses(
        id=settings.INTEGRACAR_CHAT_MODEL,
        api_key=settings.OPENAI_API_KEY,
        timeout=60,
        max_retries=2,
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
