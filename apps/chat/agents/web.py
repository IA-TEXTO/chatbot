"""Converte as citações da busca web em links visíveis na resposta."""

import re
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048
MARCADORES_WEB = re.compile(r'【[^】]+】')


def _url_segura(url: str | None) -> str | None:
    if not url or len(url) > MAX_URL_LENGTH or re.search(r'[\s<>]', url):
        return None
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {'http', 'https'}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None
    return url


def _citacoes_inline(texto: str, citacoes) -> tuple[list, list]:
    urls = []
    insercoes = []
    for item in citacoes.raw or []:
        if not isinstance(item, dict) or item.get('type') != 'url_citation':
            continue
        url = _url_segura(item.get('url'))
        posicao = item.get('end_index')
        if not url or not isinstance(posicao, int):
            continue
        if not 0 <= posicao <= len(texto):
            continue
        if url not in urls:
            urls.append(url)
        insercoes.append((posicao, urls.index(url) + 1, url))
    return urls, insercoes


def formatar_resposta_web(texto: str, citacoes) -> str | None:
    """Insere links ao lado dos trechos citados, preservando o texto gerado."""
    if not citacoes:
        return None

    urls, insercoes = _citacoes_inline(texto, citacoes)
    for posicao, numero, url in sorted(insercoes, reverse=True):
        texto = texto[:posicao] + f' [Web {numero}](<{url}>)' + texto[posicao:]
    texto = MARCADORES_WEB.sub('', texto)

    if insercoes:
        return texto

    for fonte in citacoes.urls or []:
        url = _url_segura(fonte.url)
        if url and url not in urls:
            urls.append(url)
    if not urls:
        return None

    links = '\n'.join(
        f'- [Web {numero}](<{url}>)'
        for numero, url in enumerate(urls, start=1)
    )
    return f'{texto}\n\nFontes na internet:\n{links}'
