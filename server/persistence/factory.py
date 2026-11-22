"""Composição de conexão, coleção não particionada, migração e serviço."""

from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, PyMongoError

from server.persistence.migrations import migrar
from server.persistence.mongo import BancoIndisponivel, MongoStore
from server.services import Livraria


def criar_livraria_mongo(config):
    client = None
    try:
        client = MongoClient(
            config['MONGODB_URI'], retryWrites=False,
            serverSelectionTimeoutMS=4000, connectTimeoutMS=4000,
            socketTimeoutMS=8000, maxPoolSize=20, appname='entrelinhas-nosql',
        )
        client.admin.command('ping')
        database = client[config['MONGODB_DATABASE']]
        nome = config['MONGODB_COLLECTION']
        try:
            database.create_collection(nome)
        except CollectionInvalid:
            pass
        collection = database[nome]
        collection.create_index('tipo', name='por_tipo')
        loja = Livraria()
        store = MongoStore(loja, collection)
        migrar(loja)
        return loja, store
    except (PyMongoError, BancoIndisponivel):
        if client is not None:
            client.close()
        raise RuntimeError('Não foi possível iniciar o MongoDB. Confira a configuração e a disponibilidade do banco.') from None
