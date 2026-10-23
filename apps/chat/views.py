import re
from collections.abc import Iterable
from pathlib import Path

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django_q.tasks import async_task
from inertia import render, share

from chat.agents.skills import serializar_skill
from chat.export import exportar_markdown, selecionar_ramificacao
from chat.forms import ImportarDocumentosForm, ImportarSkillForm
from chat.models import (
    Conversa,
    Documento,
    Mensagem,
    Skill,
    StatusDocumento,
)
from chat.tasks import gerar_skill_de_pdf, nome_skill_disponivel


def montar_arvore_mensagens(
    mensagens: Iterable[Mensagem],
) -> dict[int, dict]:
    mensagens_ordenadas = list(mensagens)
    map_mensagens = {
        mensagem.id: {
            'id': mensagem.id,
            'conteudo': mensagem.conteudo,
            'fontes': getattr(mensagem, 'fontes', []),
            'skill': getattr(mensagem, 'skill', ''),
            'tipo': mensagem.tipo,
            'mensagem_pai': mensagem.mensagem_pai_id,
            'mensagens_filhas': [],
            'curtido': mensagem.curtido,
        }
        for mensagem in mensagens_ordenadas
    }

    for mensagem in mensagens_ordenadas:
        if mensagem.mensagem_pai_id in map_mensagens:
            map_mensagens[mensagem.mensagem_pai_id]['mensagens_filhas'].append(
                mensagem.id
            )

    return map_mensagens


class BaseChatView(View):
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class IndexView(BaseChatView):
    def get(self, request: HttpRequest):
        return render(request, 'Index')


@method_decorator(login_required, name='dispatch')
class ConversaView(BaseChatView):
    def _gerar_map_mensagens(self, conversa: Conversa):
        mensagens = Mensagem.objects.filter(conversa=conversa).order_by(
            'criado_em',
            'id',
        )
        return montar_arvore_mensagens(mensagens)

    def get(self, request: HttpRequest, id_conversa: int):
        if request.user.is_superuser:
            qs = Conversa.objects.all()
        else:
            qs = Conversa.objects.filter(
                usuario=request.user,
            )

        conversa = get_object_or_404(qs, id=id_conversa)

        conversa.visitada_em = timezone.now()
        conversa.save(update_fields=['visitada_em'])

        share(
            request=request,
            id_conversa=conversa.id,
            map_mensagens=self._gerar_map_mensagens(conversa),
        )

        return render(request, 'Index')


@method_decorator([login_required, csrf_exempt], name='dispatch')
class DocumentosView(View):
    template_name = 'Chat/Documentos'
    form_class = ImportarDocumentosForm

    def get(self, request: HttpRequest, extra_context=None):
        documentos = Documento.objects.all()

        documentos_processados = documentos.filter(
            status=StatusDocumento.PROCESSADO
        ).count()

        documentos_pendentes = documentos.filter(
            status__in=[
                StatusDocumento.PENDENTE,
                StatusDocumento.PROCESSANDO,
            ]
        ).count()

        context = {
            'importar_documentos_form': ImportarDocumentosForm(),
            'documentos': documentos,
            'documentos_processados': documentos_processados,
            'documentos_pendentes': documentos_pendentes,
        } | (extra_context or {})
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest):
        arquivos = {
            'documentos': [
                doc
                for name, doc in request.FILES.items()
                if re.compile(r'^documentos\[\d+\]$').match(name)
            ]
        }

        # Extrair os tipos de documentos do POST
        tipos = {}
        for key, value in request.POST.items():
            match = re.compile(r'^tipos\[(\d+)\]$').match(key)
            if match:
                tipos[match.group(1)] = value

        form = self.form_class({}, arquivos)
        if not form.is_valid():
            return self.get(request, {'importar_documentos_form': form})

        form.save(tipos=tipos)

        return redirect('documentos')


class ExcluirDocumentoView(View):
    def post(self, request: HttpRequest, id_documento: int):
        documento = get_object_or_404(Documento, id=id_documento)
        documento.delete()
        return redirect('documentos')


@method_decorator(login_required, name='dispatch')
class ExcluirConversaView(View):
    def post(self, request: HttpRequest, id_conversa: int):
        conversa = get_object_or_404(
            Conversa,
            id=id_conversa,
            usuario=request.user,
        )
        conversa.delete()

        referer = request.META.get('HTTP_REFERER', '')
        if f'/c/{id_conversa}/' in referer:
            return redirect('index')

        return redirect(referer or 'index')


apenas_staff = [
    login_required,
    user_passes_test(lambda usuario: usuario.is_staff),
]


@method_decorator([*apenas_staff, csrf_exempt], name='dispatch')
class SkillsView(View):
    template_name = 'Chat/Skills'

    def get(self, request: HttpRequest, erro_importacao: str = ''):
        return render(
            request,
            self.template_name,
            {
                'skills': [
                    serializar_skill(skill) for skill in Skill.objects.all()
                ],
                'erro_importacao': erro_importacao,
            },
        )

    def post(self, request: HttpRequest):
        form = ImportarSkillForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.get(request, 'Envie um arquivo PDF.')

        arquivo = form.cleaned_data['arquivo']
        skill = Skill.objects.create(
            nome=nome_skill_disponivel(Path(arquivo.name).stem),
            arquivo_origem=arquivo,
            status=Skill.Status.GERANDO,
        )
        transaction.on_commit(lambda: async_task(gerar_skill_de_pdf, skill.id))
        return redirect('skills')


@method_decorator([*apenas_staff, csrf_exempt], name='dispatch')
class ExcluirSkillView(View):
    def post(self, request: HttpRequest, id_skill: int):
        get_object_or_404(Skill, id=id_skill).delete()
        return redirect('skills')


@method_decorator(login_required, name='dispatch')
class ExportarConversaView(View):
    def get(self, request: HttpRequest, id_conversa: int):
        conversa = get_object_or_404(
            Conversa, id=id_conversa, usuario=request.user
        )
        try:
            id_ultima = int(request.GET.get('ultima_mensagem', ''))
            mensagens = selecionar_ramificacao(
                conversa.mensagens.order_by('criado_em', 'id'), id_ultima
            )
        except (ValueError, ValidationError):
            return HttpResponseBadRequest(
                'Selecione uma versão válida da conversa.'
            )
        resposta = HttpResponse(
            exportar_markdown(conversa, mensagens),
            content_type='text/markdown; charset=utf-8',
        )
        resposta['Content-Disposition'] = (
            f'attachment; filename="integracar-conversa-{conversa.id}.md"'
        )
        resposta['Cache-Control'] = 'private, no-store'
        return resposta
