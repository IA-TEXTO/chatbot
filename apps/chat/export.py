"""Exportação de uma ramificação da conversa, sem misturar versões editadas."""

from django.core.exceptions import ValidationError
from django.utils import timezone


def selecionar_ramificacao(mensagens, id_ultima_mensagem):
    por_id = {mensagem.id: mensagem for mensagem in mensagens}
    caminho = []
    visitados = set()
    atual = id_ultima_mensagem
    while atual is not None:
        if atual in visitados or atual not in por_id:
            raise ValidationError('A versão selecionada não está disponível.')
        visitados.add(atual)
        mensagem = por_id[atual]
        caminho.append(mensagem)
        atual = mensagem.mensagem_pai_id
    return list(reversed(caminho))


def exportar_markdown(conversa, mensagens):
    linhas = [
        f'# {conversa.nome}',
        '',
        'Consulta ao Chatbot IntegraCAR',
        f'Exportada em {timezone.localtime():%d/%m/%Y %H:%M}',
        '',
        'As respostas foram geradas por IA. Confira os documentos citados antes de tomar decisões.',
    ]
    for mensagem in mensagens:
        autor = 'Você' if mensagem.tipo == 'USUARIO' else 'IntegraCAR'
        linhas.extend(['', f'## {autor}', '', mensagem.conteudo])
        if mensagem.tipo == 'ASSISTENTE' and mensagem.fontes:
            linhas.extend(['', '### Fontes recuperadas', ''])
            for fonte in mensagem.fontes:
                linhas.extend([
                    f'#### Fonte {fonte.get("numero", "?")}: {fonte.get("nome", "Documento")}',
                    '',
                    str(fonte.get('trecho', '')),
                    '',
                ])
    return '\n'.join(linhas) + '\n'
