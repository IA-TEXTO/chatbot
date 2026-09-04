from ninja import ModelSchema, Schema

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
