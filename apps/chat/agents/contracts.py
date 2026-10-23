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
    needs_web: bool = False
    clarification_question: str | None = None
    skill: str | None = Field(
        default=None,
        description='Nome da skill do catálogo, somente quando se aplica.',
    )
    rationale: str = Field(
        description='Justificativa curta, usada apenas para observabilidade.',
    )


class SkillGerada(BaseModel):
    nome: str = Field(
        description='Identificador curto em minúsculas, com hífens.',
    )
    titulo: str
    documento: str = Field(
        description='Nome oficial do documento, como aparece nele.',
    )
    descricao: str = Field(
        description='Quando a skill se aplica e quando não se aplica.',
    )
    rotas: list[Route]
    linha_de_raciocinio: str = Field(
        description='Lista numerada em markdown com os passos de raciocínio.',
    )
    referencia: str = Field(
        description='Conteúdo do documento reorganizado em markdown.',
    )
    pontos_a_revisar: list[str] = Field(
        description='Inconsistências ou ambiguidades para o curador conferir.',
    )
