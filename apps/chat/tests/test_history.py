# ruff: noqa: S101, PLR2004, PT027
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import RequestFactory
from ninja.errors import HttpError
from pydantic import ValidationError as SchemaValidationError

from chat.api import renomear_conversa
from chat.export import exportar_markdown, selecionar_ramificacao
from chat.schemas import RenomearConversaSchema
from chat.views import ExportarConversaView


def mensagem(id_, pai=None, tipo='USUARIO', conteudo='Pergunta', fontes=None):
    return SimpleNamespace(
        id=id_,
        mensagem_pai_id=pai,
        tipo=tipo,
        conteudo=conteudo,
        fontes=fontes or [],
    )


class HistoryTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=42, is_authenticated=True)

    def test_export_follows_selected_branch(self):
        mensagens = [
            mensagem(1),
            mensagem(2, 1, 'ASSISTENTE'),
            mensagem(3, 2, conteudo='Original'),
            mensagem(4, 3, 'ASSISTENTE'),
            mensagem(5, 2, conteudo='Editada'),
            mensagem(6, 5, 'ASSISTENTE'),
        ]
        assert [m.id for m in selecionar_ramificacao(mensagens, 4)] == [
            1,
            2,
            3,
            4,
        ]
        assert [m.id for m in selecionar_ramificacao(mensagens, 6)] == [
            1,
            2,
            5,
            6,
        ]

    def test_invalid_paths_are_rejected(self):
        for mensagens, ultima in [
            ([mensagem(1)], 999),
            ([mensagem(1, 2), mensagem(2, 1)], 2),
            ([mensagem(1, 999)], 1),
        ]:
            with self.subTest(ultima=ultima, mensagens=mensagens):
                with self.assertRaises(ValidationError):
                    selecionar_ramificacao(mensagens, ultima)

    def test_export_preserves_markdown_and_evidence(self):
        texto = exportar_markdown(
            SimpleNamespace(nome='Consulta APP'),
            [
                mensagem(1, conteudo='Como preencher?'),
                mensagem(
                    2,
                    1,
                    'ASSISTENTE',
                    '**Confira** [Fonte 1]',
                    [
                        {
                            'numero': 1,
                            'nome': 'Manual.pdf',
                            'trecho': 'Trecho verificável.',
                        }
                    ],
                ),
            ],
        )
        assert '# Consulta APP' in texto
        assert '## Você' in texto
        assert '**Confira** [Fonte 1]' in texto
        assert 'Fonte 1: Manual.pdf' in texto
        assert 'Trecho verificável.' in texto

    def test_name_validation(self):
        assert (
            RenomearConversaSchema(nome='  Minha consulta  ').nome
            == 'Minha consulta'
        )
        for nome in ['', '   ', 'x' * 51]:
            with self.subTest(nome=nome):
                with self.assertRaises(SchemaValidationError):
                    RenomearConversaSchema(nome=nome)

    def test_anonymous_cannot_rename(self):
        request = self.factory.patch('/api/conversas/1')
        request.user = AnonymousUser()
        with self.assertRaises(HttpError) as erro:
            renomear_conversa(
                request, 1, RenomearConversaSchema(nome='Consulta')
            )
        assert erro.exception.status_code == 403

    @patch('chat.api.get_object_or_404')
    def test_rename_is_scoped_to_owner(self, obter):
        request = self.factory.patch('/api/conversas/7')
        request.user = self.user
        conversa = obter.return_value
        conversa.id = 7
        result = renomear_conversa(
            request, 7, RenomearConversaSchema(nome='Novo nome')
        )
        assert obter.call_args.kwargs == {'id': 7, 'usuario': self.user}
        assert result == {'id': 7, 'nome': 'Novo nome'}
        conversa.save.assert_called_once_with(update_fields=['nome'])

    @patch('chat.views.get_object_or_404')
    def test_export_has_download_headers_and_owner_filter(self, obter):
        request = self.factory.get('/c/7/exportar/?ultima_mensagem=2')
        request.user = self.user
        conversa = obter.return_value
        conversa.id = 7
        conversa.nome = 'Minha consulta'
        conversa.mensagens.order_by.return_value = [
            mensagem(1),
            mensagem(2, 1, 'ASSISTENTE'),
        ]
        response = ExportarConversaView.as_view()(request, id_conversa=7)
        assert obter.call_args.kwargs == {'id': 7, 'usuario': self.user}
        assert response.status_code == 200
        assert (
            response['Content-Disposition']
            == 'attachment; filename="integracar-conversa-7.md"'
        )
        assert response['Cache-Control'] == 'private, no-store'
        assert 'Minha consulta' in response.content.decode()

    @patch('chat.views.get_object_or_404')
    def test_export_rejects_invalid_selection(self, obter):
        obter.return_value.mensagens.order_by.return_value = [mensagem(1)]
        for query in ['', '?ultima_mensagem=abc', '?ultima_mensagem=999']:
            request = self.factory.get('/c/7/exportar/' + query)
            request.user = self.user
            assert (
                ExportarConversaView.as_view()(
                    request, id_conversa=7
                ).status_code
                == 400
            )

    def test_anonymous_export_redirects_to_login(self):
        request = self.factory.get('/c/7/exportar/?ultima_mensagem=1')
        request.user = AnonymousUser()
        response = ExportarConversaView.as_view()(request, id_conversa=7)
        assert response.status_code == 302
        assert 'next=' in response.url

    @patch('chat.views.get_object_or_404', side_effect=Http404)
    def test_foreign_export_does_not_return_content(self, obter):
        request = self.factory.get('/c/7/exportar/?ultima_mensagem=1')
        request.user = self.user
        with self.assertRaises(Http404):
            ExportarConversaView.as_view()(request, id_conversa=7)
