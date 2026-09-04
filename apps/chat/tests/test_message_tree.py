# ruff: noqa: PLR2004, S101

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from chat.api import _obter_mensagem_pai
from chat.models import Mensagem
from chat.schemas import ChatSchema
from chat.views import montar_arvore_mensagens


def mensagem(id_, tipo, pai=None, conteudo=''):
    return SimpleNamespace(
        id=id_,
        tipo=tipo,
        mensagem_pai_id=pai,
        conteudo=conteudo,
        curtido=None,
    )


class MessageTreeTests(TestCase):
    def test_edited_message_creates_sibling_branches(self):
        mensagens = [
            mensagem(1, Mensagem.OpcoesTipo.USUARIO, conteudo='Original'),
            mensagem(2, Mensagem.OpcoesTipo.ASSISTENTE, 1),
            mensagem(3, Mensagem.OpcoesTipo.USUARIO, 2, 'Primeira versão'),
            mensagem(4, Mensagem.OpcoesTipo.ASSISTENTE, 3),
            mensagem(5, Mensagem.OpcoesTipo.USUARIO, 2, 'Versão editada'),
            mensagem(6, Mensagem.OpcoesTipo.ASSISTENTE, 5),
        ]

        arvore = montar_arvore_mensagens(mensagens)

        assert arvore[2]['mensagens_filhas'] == [3, 5]
        assert arvore[3]['mensagens_filhas'] == [4]
        assert arvore[5]['mensagens_filhas'] == [6]
        assert arvore[3]['conteudo'] == 'Primeira versão'
        assert arvore[5]['conteudo'] == 'Versão editada'

    @patch('chat.api.get_object_or_404')
    def test_edit_uses_original_message_parent(self, get_object_or_404):
        original = SimpleNamespace(id=8, mensagem_pai_id=7)
        parent = SimpleNamespace(id=7)
        get_object_or_404.side_effect = [original, parent]
        conversa = SimpleNamespace(id=3)
        payload = ChatSchema(
            mensagem='Versão editada',
            id_conversa=3,
            id_mensagem_pai=999,
            id_mensagem_editada=8,
        )

        result = _obter_mensagem_pai(conversa, payload)

        assert result is parent
        assert get_object_or_404.call_count == 2
        assert get_object_or_404.call_args_list[1].kwargs['id'] == 7
        assert (
            get_object_or_404.call_args_list[1].kwargs['tipo']
            == Mensagem.OpcoesTipo.ASSISTENTE
        )

    @patch('chat.api.get_object_or_404')
    def test_editing_root_message_keeps_new_version_at_root(
        self,
        get_object_or_404,
    ):
        get_object_or_404.return_value = SimpleNamespace(
            id=1,
            mensagem_pai_id=None,
        )
        conversa = SimpleNamespace(id=3)
        payload = ChatSchema(
            mensagem='Nova raiz',
            id_conversa=3,
            id_mensagem_editada=1,
        )

        result = _obter_mensagem_pai(conversa, payload)

        assert result is None
        assert get_object_or_404.call_count == 1
