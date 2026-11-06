# ruff: noqa: S101, PLR2004

from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from chat.agents.skills import serializar_skill
from chat.forms import ImportarSkillForm
from chat.models import Skill
from chat.tasks import gerar_skill_de_pdf
from chat.views import SkillsView


def pdf(nome='manual.pdf'):
    return SimpleUploadedFile(nome, b'%PDF-1.4 teste', 'application/pdf')


class ImportarSkillTests(TestCase):
    def test_formulario_aceita_um_ou_varios_pdfs(self):
        for arquivos in ([pdf()], [pdf(), pdf('norma.PDF')]):
            request = RequestFactory().post('/', {'arquivo': arquivos})
            form = ImportarSkillForm(request.POST, request.FILES)

            assert form.is_valid(), form.errors
            assert len(form.cleaned_data['arquivo']) == len(arquivos)

    def test_formulario_rejeita_lista_vazia_ou_qualquer_arquivo_invalido(self):
        for arquivos in ([], [pdf(), pdf('invalido.txt')]):
            request = RequestFactory().post('/', {'arquivo': arquivos})
            form = ImportarSkillForm(request.POST, request.FILES)

            assert not form.is_valid()

    @patch('chat.views.redirect')
    @patch('chat.views.async_task')
    @patch('chat.views.transaction.on_commit')
    @patch('chat.views.transaction.atomic', new=nullcontext)
    @patch('chat.views.DocumentoSkill.objects.create')
    @patch('chat.views.Skill.objects.create')
    @patch('chat.views.nome_skill_disponivel', new=lambda _base: 'manual')
    def test_upload_cria_uma_skill_e_agenda_uma_tarefa_apos_salvar_todos(
        self,
        criar_skill,
        criar_documento,
        on_commit,
        task,
        redirect,
    ):
        request = RequestFactory().post(
            '/', {'arquivo': [pdf(), pdf('norma.pdf')]}
        )
        skill = criar_skill.return_value
        skill.id = 42

        SkillsView().post(request)

        criar_skill.assert_called_once_with(
            nome='manual', status=Skill.Status.GERANDO
        )
        assert criar_documento.call_count == 2
        assert [
            chamada.kwargs['nome']
            for chamada in criar_documento.call_args_list
        ] == ['manual.pdf', 'norma.pdf']
        assert all(
            chamada.kwargs['skill'] is skill
            for chamada in criar_documento.call_args_list
        )
        task.assert_not_called()
        on_commit.assert_called_once()
        on_commit.call_args.args[0]()
        task.assert_called_once_with(gerar_skill_de_pdf, 42)

    @patch.object(SkillsView, 'get')
    @patch('chat.views.Skill.objects.create')
    def test_upload_invalido_nao_cria_skill(self, criar, get):
        request = RequestFactory().post(
            '/', {'arquivo': [pdf(), pdf('invalido.txt')]}
        )

        SkillsView().post(request)

        criar.assert_not_called()
        get.assert_called_once()


class GerarSkillTests(TestCase):
    @patch('chat.tasks.Skill.objects')
    @patch('chat.tasks.PyPDFLoader')
    @patch('chat.tasks.build_skill_writer')
    @patch(
        'chat.tasks.nome_skill_disponivel', return_value='contexto-unificado'
    )
    def test_analisa_todos_os_pdfs_sem_cortar_texto_em_uma_unica_geracao(
        self,
        nome,
        writer,
        loader,
        skills,
    ):
        skills.get.return_value = SimpleNamespace(
            id=42,
            pdfs_origem=[
                ('manual.pdf', SimpleNamespace(path='/manual.pdf')),
                ('norma.pdf', SimpleNamespace(path='/norma.pdf')),
            ],
        )
        texto_longo = 'A' * 40_001 + ' FINAL DO MANUAL'
        loader.return_value.load.side_effect = [
            [SimpleNamespace(page_content=texto_longo)],
            [SimpleNamespace(page_content='REGRA DA NORMA')],
        ]
        writer.return_value.run.return_value.content = {
            'nome': 'contexto-unificado',
            'titulo': 'Contexto unificado',
            'documento': 'Manual e Norma',
            'descricao': 'Procedimentos e normas do cadastro.',
            'rotas': ['manual', 'mista'],
            'linha_de_raciocinio': '1. Consulte os documentos.',
            'referencia': '### Manual\nEtapas.\n### Norma\nRegras.',
            'pontos_a_revisar': [],
        }

        gerar_skill_de_pdf(42)

        writer.return_value.run.assert_called_once()
        prompt = writer.return_value.run.call_args.args[0]
        assert texto_longo in prompt
        assert 'REGRA DA NORMA' in prompt
        assert '<nome>manual.pdf</nome>' in prompt
        assert '<nome>norma.pdf</nome>' in prompt
        assert loader.call_count == 2
        atualizacao = skills.filter.return_value.update.call_args.kwargs
        assert atualizacao['status'] == Skill.Status.RASCUNHO
        assert 'Manual e Norma' in atualizacao['conteudo']

    @patch('chat.tasks.Skill.objects')
    @patch('chat.tasks.PyPDFLoader')
    @patch('chat.tasks.build_skill_writer')
    def test_pdf_sem_texto_impede_geracao_parcial(
        self, writer, loader, skills
    ):
        skills.get.return_value = SimpleNamespace(
            id=42,
            pdfs_origem=[
                ('manual.pdf', SimpleNamespace(path='/manual.pdf')),
                ('escaneado.pdf', SimpleNamespace(path='/escaneado.pdf')),
            ],
        )
        loader.return_value.load.side_effect = [
            [SimpleNamespace(page_content='Texto válido')],
            [SimpleNamespace(page_content='  ')],
        ]

        gerar_skill_de_pdf(42)

        writer.assert_not_called()
        atualizacao = skills.filter.return_value.update.call_args.kwargs
        assert atualizacao['status'] == Skill.Status.ERRO
        assert 'escaneado.pdf' in atualizacao['observacoes']


class SkillOrigensTests(TestCase):
    def test_origens_incluem_pdf_legado_e_novos_documentos(self):
        legado = SimpleNamespace(name='skills/legado.pdf', url='/legado.pdf')
        novo = SimpleNamespace(nome='novo.pdf', arquivo=Mock())
        skill = SimpleNamespace(
            arquivo_origem=legado,
            documentos_origem=Mock(),
        )
        skill.documentos_origem.all.return_value = [novo]

        assert Skill.pdfs_origem.fget(skill) == [
            ('legado.pdf', legado),
            ('novo.pdf', novo.arquivo),
        ]

    def test_serializacao_expoe_todos_os_pdfs(self):
        skill = SimpleNamespace(
            id=42,
            nome='manual',
            arquivo='manual.md',
            conteudo='',
            status=Skill.Status.GERANDO,
            observacoes='',
            pdfs_origem=[
                ('manual.pdf', SimpleNamespace(url='/manual.pdf')),
                ('norma.pdf', SimpleNamespace(url='/norma.pdf')),
            ],
        )

        dados = serializar_skill(skill)

        assert dados['arquivos_origem'] == [
            {'nome': 'manual.pdf', 'url': '/manual.pdf'},
            {'nome': 'norma.pdf', 'url': '/norma.pdf'},
        ]
        assert dados['arquivo_origem'] == '/manual.pdf'
