from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


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
    complementary_queries: list[str] = Field(
        default_factory=list,
        max_length=2,
        description=(
            'Até duas buscas curtas e autossuficientes para aspectos distintos '
            'da pergunta ou termos alternativos. Vazio em perguntas simples.'
        ),
    )
    needs_clarification: bool = False
    needs_web: bool = False
    clarification_question: str | None = None
    rationale: str = Field(
        description='Justificativa curta, usada apenas para observabilidade.',
    )

    @field_validator('rewritten_query')
    @classmethod
    def validar_busca_principal(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError('A busca principal não pode ser vazia.')
        return valor

    @field_validator('complementary_queries')
    @classmethod
    def limpar_buscas(cls, valores: list[str]) -> list[str]:
        return [valor.strip()[:300] for valor in valores if valor.strip()]
