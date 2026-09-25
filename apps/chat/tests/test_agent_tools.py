# ruff: noqa: S101, PLR2004

import json
from queue import Queue
from unittest import TestCase
from unittest.mock import patch

from agno.run import RunContext

from chat.agents.tools import (
    EvidenceContext,
    buscar_fontes,
    consultar_trecho,
    validar_citacoes,
)
from chat.api import _stream_resposta, _transmitir_eventos
from chat.models import Documento
from chat.rag import RetrievedChunk


def fonte(
    conteudo: str, documento_id: int = 1, tipo: str = Documento.Tipo.MANUAL
) -> RetrievedChunk:
    return RetrievedChunk(
        conteudo=conteudo,
        documento_id=documento_id,
        documento_nome=f'Documento {documento_id}',
        documento_tipo=tipo,
        score=0.1,
    )


class FerramentasDosAgentesTests(TestCase):
    def test_busca_complementar_preserva_numeros_e_limites(self):
        chamadas = []
        publicadas = []
        etapas = []

        def recuperar(query, k):
            chamadas.append((query, k))
            return [
                fonte('Trecho inicial'),
                fonte('Novo trecho', 2, Documento.Tipo.LEGISLACAO),
            ]

        contexto = EvidenceContext(
            fontes=[fonte('Trecho inicial')],
            retriever=recuperar,
            on_sources=publicadas.append,
            on_progress=etapas.append,
        )
        run = RunContext(
            run_id='teste',
            session_id='teste',
            dependencies={'evidence_context': contexto},
        )

        primeira = buscar_fontes('  APP  ', run_context=run)
        segunda = buscar_fontes('Reserva legal', run_context=run)
        terceira = buscar_fontes('Mais fontes', run_context=run)

        assert primeira['fontes_novas'][0]['numero'] == 2
        assert primeira['fontes_novas'][0]['tipo'] == Documento.Tipo.LEGISLACAO
        assert segunda['fontes_novas'] == []
        assert 'erro' in terceira
        assert chamadas[0] == ('APP', 6)
        assert [item['numero'] for item in publicadas[-1]] == [1, 2]
        assert consultar_trecho(2, run_context=run)['trecho'] == 'Novo trecho'
        assert len(etapas) == 4

    def test_citacao_invalida_fica_identificavel(self):
        resposta = validar_citacoes(
            'Correto [Fonte 1]. Incerto [Fonte 9]. (fonte 1, 7)', 2
        )
        assert '[Fonte 1]' in resposta
        assert '[citação não verificada]' in resposta
        assert 'Confira a orientação' in resposta
        assert validar_citacoes('Ok [Fonte 1].', 1) == 'Ok [Fonte 1].'

    def test_stream_mantem_etapas_separadas_do_texto(self):
        eventos = Queue()
        eventos.put(('progresso', 'Buscando fontes...'))
        eventos.put(('trecho', 'Resposta'))
        eventos.put(('fim', None))
        partes = []

        enviados = list(_transmitir_eventos(eventos, partes, []))

        assert enviados[0] == {
            'tipo': 'progresso',
            'conteudo': 'Buscando fontes...',
        }
        assert partes == ['Resposta']

    @patch('chat.agents.tools.RespostaCanonica.objects')
    def test_resposta_canonica_nao_vira_fonte_documental(self, objetos):
        objetos.filter.return_value.values.return_value.__getitem__.return_value = [
            {'pergunta': 'Como iniciar CAR?', 'resposta': 'Confira o roteiro.'}
        ]
        contexto = EvidenceContext(
            fontes=[fonte('Trecho inicial')],
            retriever=lambda *_: [],
        )

        resultado = contexto.canonica('Como iniciar CAR?')

        assert resultado['respostas'][0]['orientacao'] == 'Confira o roteiro.'
        assert len(contexto.fontes) == 1

    @patch('chat.api.Mensagem.objects')
    def test_stream_transmite_progresso_e_resposta_final_validada(
        self, objetos
    ):
        fontes = [{'numero': 1, 'documento_id': 1, 'nome': 'Manual'}]

        def gerar(on_progress, on_final):
            on_progress('Buscando fontes...')
            yield 'Resposta [Fonte 2].'

        linhas = list(
            _stream_resposta({'id_mensagem_resposta': 8}, gerar, fontes, 8)
        )
        eventos = [json.loads(linha) for linha in linhas]

        assert eventos[1] == {
            'tipo': 'progresso',
            'conteudo': 'Buscando fontes...',
        }
        assert eventos[2]['tipo'] == 'trecho'
        assert 'citação não verificada' in eventos[-2]['conteudo']
        objetos.filter.return_value.update.assert_called_once()

    @patch('chat.api.Mensagem.objects')
    def test_stream_substitui_texto_web_pela_versao_com_links(self, objetos):
        def gerar(on_progress, on_final):
            yield 'Resposta da web.'
            on_final('Resposta da web. [Web 1](<https://idaf.es.gov.br>)')

        linhas = list(_stream_resposta({}, gerar, [], 9))
        eventos = [json.loads(linha) for linha in linhas]

        assert eventos[1] == {'tipo': 'trecho', 'conteudo': 'Resposta da web.'}
        assert eventos[-2]['conteudo'].endswith(
            '[Web 1](<https://idaf.es.gov.br>)'
        )
        assert (
            objetos.filter.return_value.update.call_args.kwargs['conteudo']
            == (eventos[-2]['conteudo'])
        )
