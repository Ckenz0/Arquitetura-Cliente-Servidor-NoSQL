"""Persistência real, transações e reinício entre instâncias independentes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier
from uuid import uuid4

import pytest
from pymongo import MongoClient

from server.demonstracao import criar_demonstracao
from server.domain.regras import ErroLivraria


@pytest.fixture
def colecao_mongo():
    uri = os.environ.get('TEST_MONGODB_URI')
    if not uri:
        pytest.skip('Defina TEST_MONGODB_URI para testar um MongoDB replica set real.')
    client = MongoClient(uri, serverSelectionTimeoutMS=3000, retryWrites=False)
    client.admin.command('ping')
    database = client[f'entrelinhas_test_{uuid4().hex}']
    collection = database.create_collection('livraria')
    try:
        yield collection
    finally:
        client.drop_database(database.name)
        client.close()


def loja_persistente(collection):
    from server.persistence.mongo import MongoStore
    loja = criar_demonstracao()
    MongoStore(loja, collection)
    return loja


def preparar(collection):
    from server.persistence.migrations import migrar
    loja = loja_persistente(collection)
    migrar(loja)
    return loja


def prazo():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


@pytest.mark.mongo
def test_todos_os_dados_sobrevivem_nova_instancia(colecao_mongo):
    loja = preparar(colecao_mongo)
    evento = loja.eventos()[0]['id']
    clube = loja.clubes('ana')[0]['id']
    horario = loja.estado('ana')['horarios'][0]['id']
    loja.preferencias('ana', ['Fantasia'], ['reservas', 'estoque', 'fidelidade'])
    loja.adicionar_desejo('ana', 'hobbit')
    reserva = loja.reservar('ana', '1984', prazo(), True)
    loja.alterar_prazo('ana', reserva['id'], prazo())
    loja.marcar_pronta(reserva['id'])
    loja.acompanhar_estoque('ana', 'esgotado')
    loja.atualizar_estoque('esgotado', 2)
    loja.registrar_compra('ana', 'hobbit', 42)
    loja.conceder_cupom('ana', 'LEITURA', 'Na loja')
    loja.entrar_fila('ana')
    loja.agendar('ana', horario)
    loja.inscrever('ana', evento)
    loja.participar_clube('ana', clube)
    loja.publicar_opiniao('ana', clube, 'Vamos ler juntos.')
    loja.publicar_avaliacao('ana', '1984', 5, 'Uma ótima leitura.')
    loja.configurar_loja('Todos os dias', 25)

    outra = loja_persistente(colecao_mongo)
    estado = outra.estado('ana')
    assert estado['cliente']['generos'] == ['Fantasia']
    assert estado['cliente']['temas_notificacao'] == ['reservas', 'estoque', 'fidelidade']
    assert estado['reservas'][0]['status'] == 'pronta'
    assert estado['reservas'][0]['embrulho'] is True
    assert outra.livro('1984', 'ana')['estoque'] == 2
    assert outra.livro('1984', 'ana')['ja_avaliou'] is True
    assert outra.livro('1984')['avaliacoes'][-1]['nota'] == 5
    assert [livro['id'] for livro in estado['desejos']] == ['hobbit']
    assert estado['fidelidade']['saldo'] == 42
    assert estado['fidelidade']['cupons'][0]['codigo'] == 'LEITURA'
    assert estado['historico'][0]['livro']['id'] == 'hobbit'
    assert estado['fila']['posicao'] == 1
    assert estado['agendamentos'][0]['id'] == horario
    assert estado['eventos'][0]['inscrito'] is True
    assert estado['clubes'][0]['participando'] is True
    assert estado['clubes'][0]['opinioes'][0]['texto'] == 'Vamos ler juntos.'
    assert estado['loja'] == {'horario': 'Todos os dias', 'lotacao': 25}
    assert {n['tema'] for n in estado['notificacoes']} == {'reservas', 'estoque', 'fidelidade'}
    assert outra.estado('bia')['reservas'] == []
    assert outra.estado('bia')['desejos'] == []
    assert outra.buscar_por_titulo('1984')[0]['estoque'] == 2
    assert colecao_mongo.count_documents({'tipo': 'livros'}) == 12
    assert colecao_mongo.count_documents({'tipo': 'reservas'}) == 1
    with pytest.raises(ErroLivraria, match='já publicou'):
        outra.publicar_avaliacao('ana', '1984', 3, 'Repetida.')
    outra.cancelar_reserva('ana', reserva['id'])
    loja.cancelar_reserva('ana', reserva['id'])
    assert outra.livro('1984')['estoque'] == 3


@pytest.mark.mongo
def test_erro_aborta_estoque_reserva_e_notificacao(colecao_mongo):
    loja = preparar(colecao_mongo)
    def operacao():
        loja.reservar('ana', '1984', prazo())
        loja.conceder_cupom('ana', 'ERRO', 'Não deve persistir')
        raise ValueError('interrompido')
    with pytest.raises(ValueError, match='interrompido'):
        loja.persistencia.executar(operacao)
    outra = loja_persistente(colecao_mongo)
    assert outra.livro('1984')['estoque'] == 3
    assert outra.reservas('ana') == []
    assert outra.fidelidade('ana')['cupons'] == []
    assert outra.notificacoes('ana') == []


@pytest.mark.mongo
@pytest.mark.parametrize('recurso', ['estoque', 'evento', 'horario', 'avaliacao'])
def test_concorrencia_entre_instancias_independentes(colecao_mongo, recurso):
    inicial = preparar(colecao_mongo)
    inicial.atualizar_estoque('1984', 1)
    evento = inicial.cadastrar_evento('Uma vaga', prazo(), 'Loja', capacidade=1)['id']
    horario = inicial.estado('a')['horarios'][0]['id']
    barreira = Barrier(2)
    def executar(numero):
        loja = loja_persistente(colecao_mongo)
        barreira.wait(timeout=5)
        try:
            if recurso == 'estoque':
                loja.reservar(str(numero), '1984', prazo())
            elif recurso == 'evento':
                loja.inscrever(str(numero), evento)
            elif recurso == 'horario':
                loja.agendar(str(numero), horario)
            else:
                loja.publicar_avaliacao('mesmo-cliente', '1984', 5, 'Uma leitura.')
            return 201
        except ErroLivraria as erro:
            return erro.status
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = sorted(executor.map(executar, [1, 2]))
    assert resultados == [201, 409]
    if recurso == 'estoque':
        assert inicial.livro('1984')['estoque'] == 0
        assert colecao_mongo.count_documents({'tipo': 'reservas'}) == 1


@pytest.mark.mongo
def test_leitura_nao_regrava_documentos(colecao_mongo):
    loja = preparar(colecao_mongo)
    antes = list(colecao_mongo.find())
    loja.buscar()
    loja.livro('1984')
    assert list(colecao_mongo.find()) == antes


@pytest.mark.mongo
@pytest.mark.parametrize('confirmacao', ['recuperada', 'indisponivel'])
def test_commit_incerto_nunca_repete_reserva(colecao_mongo, monkeypatch, confirmacao):
    from pymongo.errors import OperationFailure
    from pymongo.synchronous.client_session import ClientSession
    from server.persistence.mongo import BancoIndisponivel
    loja = preparar(colecao_mongo)
    commit_real = ClientSession.commit_transaction
    commits = []
    def confirmar(session):
        commits.append(session)
        if len(commits) == 1:
            commit_real(session)
        if confirmacao == 'indisponivel' or len(commits) == 1:
            raise OperationFailure('resposta perdida', details={
                'errorLabels': ['UnknownTransactionCommitResult'],
            })
        return commit_real(session)
    monkeypatch.setattr(ClientSession, 'commit_transaction', confirmar)
    if confirmacao == 'indisponivel':
        with pytest.raises(BancoIndisponivel):
            loja.reservar('ana', '1984', prazo())
    else:
        assert loja.reservar('ana', '1984', prazo())['cliente_id'] == 'ana'
    monkeypatch.setattr(ClientSession, 'commit_transaction', commit_real)
    outra = loja_persistente(colecao_mongo)
    assert outra.livro('1984')['estoque'] == 2
    assert len(outra.reservas('ana')) == 1


@pytest.mark.mongo
def test_conflitos_esgotados_nao_deixam_alteracoes(colecao_mongo, monkeypatch):
    from pymongo.errors import OperationFailure
    from pymongo.synchronous.client_session import ClientSession
    from server.persistence.mongo import BancoIndisponivel
    loja = preparar(colecao_mongo)
    commit_real = ClientSession.commit_transaction
    def conflito(session):
        raise OperationFailure('conflito', details={'errorLabels': ['TransientTransactionError']})
    monkeypatch.setattr(ClientSession, 'commit_transaction', conflito)
    with pytest.raises(BancoIndisponivel):
        loja.reservar('ana', '1984', prazo())
    monkeypatch.setattr(ClientSession, 'commit_transaction', commit_real)
    assert loja_persistente(colecao_mongo).livro('1984')['estoque'] == 3
    assert colecao_mongo.count_documents({'tipo': 'reservas'}) == 0
