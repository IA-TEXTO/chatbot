from enum import StrEnum

from pydantic import BaseModel, Field


class Route(StrEnum):
    MANUAL = 'manual'
    LEGISLACAO = 'legislacao'
    MISTA = 'mista'
    CONVERSACIONAL = 'conversacional'
    FORA_ESCOPO = 'fora_escopo'


class TriageDecision(BaseModel):
    route: Route
    confidence: float = Field(ge=0, le=1)
    rewritten_query: str = Field(min_length=1)
    needs_clarification: bool = False
    clarification_question: str | None = None
    rationale: str = Field(
        description='Justificativa curta, usada apenas para observabilidade.',
    )
