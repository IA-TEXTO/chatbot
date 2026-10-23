from django.urls import path

from chat import views

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path(
        'c/<int:id_conversa>/', views.ConversaView.as_view(), name='conversa'
    ),
    path(
        'c/<int:id_conversa>/excluir/',
        views.ExcluirConversaView.as_view(),
        name='excluir_conversa',
    ),
    path(
        'c/<int:id_conversa>/exportar/',
        views.ExportarConversaView.as_view(),
        name='exportar_conversa',
    ),
    path('documentos/', views.DocumentosView.as_view(), name='documentos'),
    path(
        'documentos/<int:id_documento>/excluir/',
        views.ExcluirDocumentoView.as_view(),
        name='excluir_documento',
    ),
    path('skills/', views.SkillsView.as_view(), name='skills'),
    path(
        'skills/<int:id_skill>/excluir/',
        views.ExcluirSkillView.as_view(),
        name='excluir_skill',
    ),
]
