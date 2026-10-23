from ninja import ModelSchema, Schema
from pydantic import Field, field_validator

from chat.models import Documento


class ChatSchema(Schema):
    mensagem: str
    stream: bool = False
    id_mensagem_pai: int | None = None
    id_mensagem_editada: int | None = None
    id_conversa: int | None = None


class CurtirMensagemSchema(Schema):
    curtido: bool | None


class AtualizarTipoDocumentoSchema(ModelSchema):
    class Meta:
        model = Documento
        fields = ['tipo']


class EditarSkillSchema(Schema):
    conteudo: str


class AlterarStatusSkillSchema(Schema):
    ativa: bool


class RenomearConversaSchema(Schema):
    nome: str = Field(min_length=1, max_length=50)

    @field_validator('nome', mode='before')
    @classmethod
    def limpar_nome(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor
