from ninja import ModelSchema, Schema
from pydantic import Field, field_validator

from chat.models import Documento


class ChatSchema(Schema):
    mensagem: str = Field(
        description='Pergunta. Espaços nas pontas são removidos.'
    )
    stream: bool = Field(
        default=False,
        description='true: fluxo NDJSON; false: uma resposta JSON completa.',
    )
    id_mensagem_pai: int | None = Field(
        default=None,
        description='ID da resposta do assistente que antecede a nova pergunta.',
    )
    id_mensagem_editada: int | None = Field(
        default=None,
        description='ID da pergunta a editar. Cria outra versão e prevalece sobre id_mensagem_pai.',
    )
    id_conversa: int | None = Field(
        default=None,
        description='Conversa existente; omitir para criar uma conversa.',
    )


class FonteSchema(Schema):
    numero: int
    documento_id: int
    nome: str
    tipo: str
    trecho: str


class RespostaChatSchema(Schema):
    id_conversa: int
    id_mensagem_pergunta: int
    id_mensagem_resposta: int
    resposta: str
    fontes: list[FonteSchema]
    skill: str


class ErroChatSchema(Schema):
    resposta: str


class ErroGeracaoChatSchema(ErroChatSchema):
    id_conversa: int
    id_mensagem_pergunta: int
    id_mensagem_resposta: int


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
