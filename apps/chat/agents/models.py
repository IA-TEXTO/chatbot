"""Compatibilidade do Agno 3.0.5 com modelos GPT-6 na Responses API."""

from agno.models.openai import OpenAIResponses


class IntegraCAROpenAIResponses(OpenAIResponses):
    def _using_reasoning_model(self) -> bool:
        """Preserva o estado do raciocínio ao continuar chamadas de ferramentas."""
        return (
            self.id == 'gpt-6'
            or self.id.startswith('gpt-6-')
            or super()._using_reasoning_model()
        )
