"""Roteiros de raciocínio (.md) ativados pela triagem em perguntas específicas.

O conteúdo de cada skill fica no banco (``chat.models.Skill``) como markdown,
com um cabeçalho entre linhas ``---``:

    ---
    titulo: Fluxo de processos digitais
    descricao: Quando aplicar a skill (lido pela triagem).
    rotas: manual, mista
    ---
    Instruções seguidas pelo especialista...

Somente skills com status ``ativa`` chegam à triagem.
"""

import logging
from dataclasses import dataclass

from chat import models
from chat.agents.contracts import Route

logger = logging.getLogger(__name__)
ROTAS_COM_SKILL = frozenset({Route.MANUAL, Route.LEGISLACAO, Route.MISTA})
CAMPOS_OBRIGATORIOS = ('titulo', 'descricao', 'rotas')


@dataclass(frozen=True)
class Skill:
    nome: str
    titulo: str
    descricao: str
    rotas: frozenset[Route]
    instrucoes: str

    @property
    def arquivo(self) -> str:
        return f'{self.nome}.md'


def ler_markdown(nome: str, texto: str) -> Skill:
    """Valida o .md de uma skill; a mensagem de erro é exibida ao curador."""
    texto = texto.strip()
    if not texto.startswith('---') or texto.count('---') < 2:  # noqa: PLR2004
        raise ValueError(
            'O arquivo deve começar com um cabeçalho entre linhas "---".'
        )
    _, cabecalho, instrucoes = texto.split('---', 2)
    campos = {}
    for linha in cabecalho.strip().splitlines():
        chave, _, valor = linha.partition(':')
        campos[chave.strip()] = valor.strip()
    faltando = [
        campo for campo in CAMPOS_OBRIGATORIOS if not campos.get(campo)
    ]
    if faltando:
        raise ValueError(f'Preencha no cabeçalho: {", ".join(faltando)}.')
    rotas = {rota.strip() for rota in campos['rotas'].split(',')}
    invalidas = rotas - ROTAS_COM_SKILL
    if invalidas:
        raise ValueError(
            f'Rotas inválidas: {", ".join(sorted(invalidas))}. '
            f'Use: {", ".join(sorted(ROTAS_COM_SKILL))}.'
        )
    if not instrucoes.strip():
        raise ValueError('Escreva as instruções da skill após o cabeçalho.')
    return Skill(
        nome=nome,
        titulo=campos['titulo'],
        descricao=campos['descricao'],
        rotas=frozenset(Route(rota) for rota in rotas),
        instrucoes=instrucoes.strip(),
    )


def montar_markdown(
    *, titulo: str, descricao: str, rotas: list[Route], instrucoes: str
) -> str:
    cabecalho = '\n'.join((
        '---',
        f'titulo: {" ".join(titulo.split())}',
        f'descricao: {" ".join(descricao.split())}',
        f'rotas: {", ".join(sorted(set(rotas)))}',
        '---',
    ))
    return f'{cabecalho}\n{instrucoes.strip()}\n'


def carregar_skills() -> dict[str, Skill]:
    skills = {}
    ativas = models.Skill.objects.filter(
        status=models.Skill.Status.ATIVA
    ).values_list('nome', 'conteudo')
    for nome, conteudo in ativas:
        try:
            skills[nome] = ler_markdown(nome, conteudo)
        except ValueError:
            logger.exception('Skill %s ativa com conteúdo inválido.', nome)
    return skills


def obter_skill(
    skills: dict[str, Skill], nome: str | None, rota: Route
) -> Skill | None:
    """Ignora nomes inventados pela triagem e skills fora da rota escolhida."""
    skill = skills.get(nome or '')
    if skill and rota in skill.rotas:
        return skill
    return None


def catalogo_skills(skills: dict[str, Skill]) -> str:
    if not skills:
        return 'Nenhuma skill disponível. Deixe skill como null.'
    linhas = '\n'.join(
        f'- {skill.nome} (rotas: {", ".join(sorted(skill.rotas))}): '
        f'{skill.descricao}'
        for skill in skills.values()
    )
    return (
        f'{linhas}\n\n'
        'Preencha skill somente quando a solicitação corresponder claramente '
        'à descrição de uma skill e a rota escolhida estiver entre as rotas '
        'dela. A maioria das perguntas não usa skill: na dúvida, deixe skill '
        'como null. Use exatamente o nome listado.'
    )


def serializar_skill(skill: models.Skill) -> dict:
    try:
        titulo = ler_markdown(skill.nome, skill.conteudo).titulo
    except ValueError:
        titulo = ''
    return {
        'id': skill.id,
        'nome': skill.nome,
        'arquivo': skill.arquivo,
        'titulo': titulo,
        'status': skill.status,
        'conteudo': skill.conteudo,
        'observacoes': skill.observacoes,
        'arquivo_origem': (
            skill.arquivo_origem.url if skill.arquivo_origem else None
        ),
    }
