"""Configuração segura e composição da API com armazenamento durável."""

import pytest
import os

from server.app import create_app
from server.config import configuracao
from tests.helpers import cliente_identificado
from tests.test_persistencia_mongo import colecao_mongo


def test_desenvolvimento_exige_mongo_por_padrao(monkeypatch):
    monkeypatch.delenv('STORAGE_BACKEND', raising=False)
    monkeypatch.delenv('MONGODB_URI', raising=False)
    assert configuracao()['STORAGE_BACKEND'] == 'mongodb'
    assert configuracao()['MONGODB_URI'].startswith('mongodb://127.0.0.1:')


@pytest.mark.parametrize('backend,uri', [('memory', ''), ('mongodb', ''), ('outro', 'mongodb://localhost')])
def test_producao_recusa_armazenamento_inseguro(monkeypatch, backend, uri):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('SECRET_KEY', 'x' * 32)
    monkeypatch.setenv('ALLOWED_ORIGINS', 'https://livraria.example')
    monkeypatch.setenv('STORAGE_BACKEND', backend)
    monkeypatch.setenv('MONGODB_URI', uri)
    with pytest.raises(ValueError):
        configuracao()


@pytest.mark.parametrize('campo,valor', [('MONGODB_DATABASE', 'db/invalido'), ('MONGODB_COLLECTION', '$errado'), ('MONGODB_URI', 'https://banco.example')])
def test_configuracao_invalida_falha_sem_expor_uri(campo, valor):
    with pytest.raises(ValueError) as erro:
        configuracao({'STORAGE_BACKEND': 'mongodb', campo: valor})
    assert valor not in str(erro.value)


def test_producao_por_override_nao_gera_secret_automaticamente(monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    with pytest.raises(ValueError, match='SECRET_KEY'):
        configuracao({'APP_ENV': 'production', 'STORAGE_BACKEND': 'mongodb',
                      'MONGODB_URI': 'mongodb://localhost',
                      'ALLOWED_ORIGINS': 'https://loja.example'})


@pytest.mark.mongo
def test_api_nova_preserva_sessao_dados_e_carga_inicial(colecao_mongo):
    config = {
        'STORAGE_BACKEND': 'mongodb',
        'MONGODB_URI': os.environ['TEST_MONGODB_URI'],
        'MONGODB_DATABASE': colecao_mongo.database.name,
        'MONGODB_COLLECTION': colecao_mongo.name,
        'SECRET_KEY': 'chave-estavel-para-teste-de-reinicio',
    }
    app = create_app(config=config)
    cliente = cliente_identificado(app)
    token = cliente.environ_base['HTTP_AUTHORIZATION']
    assert len(cliente.get('/api/livros').json) == 12
    assert colecao_mongo.count_documents({'tipo': 'livros'}) == 12
    reserva = cliente.post('/api/reservas', json={'livro_id': '1984', 'prazo': '2099-01-01T12:00:00Z'})
    assert reserva.status_code == 201
    cliente.patch('/api/preferencias', json={'generos': ['Fantasia']})
    eventos = cliente.get('/api/estado').json['eventos']
    try:
        outra = create_app(config=config)
        novo = outra.test_client()
        novo.environ_base['HTTP_AUTHORIZATION'] = token
        estado = novo.get('/api/estado')
        assert estado.status_code == 200
        assert estado.json['cliente']['generos'] == ['Fantasia']
        assert estado.json['reservas'][0]['id'] == reserva.json['id']
        assert novo.get('/api/livros/1984').json['estoque'] == 2
        assert estado.json['eventos'] == eventos
        assert estado.json['fidelidade']['saldo'] == 20
        assert len(estado.json['fidelidade']['cupons']) == 1
        assert colecao_mongo.count_documents({'tipo': 'migracoes'}) == 1
    finally:
        app.extensions['mongo'].client.close()
        if 'outra' in locals():
            outra.extensions['mongo'].client.close()


@pytest.mark.mongo
def test_indisponibilidade_retorna_503_sem_credenciais(colecao_mongo, monkeypatch):
    from pymongo.errors import AutoReconnect
    from tests.test_persistencia_mongo import preparar
    loja = preparar(colecao_mongo)
    app = create_app(livraria=loja)
    cliente = cliente_identificado(app)
    def falhar(*args, **kwargs):
        raise AutoReconnect('mongodb://usuario:segredo@servidor')
    monkeypatch.setattr(loja.persistencia.collection, 'find', falhar)
    resposta = cliente.get('/api/livros')
    assert resposta.status_code == 503
    assert 'segredo' not in resposta.get_data(as_text=True)
    assert 'mongodb://' not in resposta.get_data(as_text=True)
    assert 'X-Request-ID' in resposta.headers


@pytest.mark.mongo
def test_falha_na_sessao_nao_deixa_compra_parcial(colecao_mongo, monkeypatch):
    app = create_app(config={
        'STORAGE_BACKEND': 'mongodb', 'MONGODB_URI': os.environ['TEST_MONGODB_URI'],
        'MONGODB_DATABASE': colecao_mongo.database.name,
        'MONGODB_COLLECTION': colecao_mongo.name,
    })
    def falhar(*args):
        raise RuntimeError('falha no cupom')
    monkeypatch.setattr(app.extensions['livraria'], 'conceder_cupom', falhar)
    try:
        assert app.test_client().post('/api/sessoes', json={}).status_code == 500
        assert colecao_mongo.count_documents({'tipo': 'clientes'}) == 0
    finally:
        app.extensions['mongo'].client.close()
