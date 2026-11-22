"""Unidade de trabalho transacional em uma coleção MongoDB não particionada."""

from time import sleep

from pymongo import DeleteOne, InsertOne, ReplaceOne
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from server.domain.regras import ErroLivraria
from server.persistence.documents import exportar, restaurar


class BancoIndisponivel(ErroLivraria):
    def __init__(self):
        super().__init__('O banco de dados está indisponível. Consulte o estado antes de repetir a operação.', 503)


class MongoStore:
    """Os repositórios em memória são somente uma visão da transação atual.

    Todo estado compartilhado é lido novamente do MongoDB. O lock local impede
    compartilhar uma sessão entre threads; a transação protege entre processos.
    """

    def __init__(self, loja, collection):
        self.loja = loja
        self.collection = collection
        self.client = collection.database.client
        self._executando = False
        loja.persistencia = self

    def health(self):
        try:
            self.client.admin.command('ping')
        except PyMongoError:
            raise BancoIndisponivel() from None

    def _commit(self, session):
        for tentativa in range(3):
            try:
                session.commit_transaction()
                return
            except PyMongoError as erro:
                if not erro.has_error_label('UnknownTransactionCommitResult'):
                    raise
                if tentativa == 2:
                    # Não reexecutar o caso de uso: o servidor pode ter gravado.
                    raise BancoIndisponivel() from None

    def executar(self, operacao):
        with self.loja._lock:
            if self._executando:
                return operacao()
            self._executando = True
            try:
                for tentativa in range(3):
                    try:
                        with self.client.start_session() as session:
                            session.start_transaction(
                                read_concern=ReadConcern('snapshot'),
                                write_concern=WriteConcern('majority'),
                                max_commit_time_ms=4000,
                            )
                            try:
                                # Cosmos tem campos internos que não são do domínio.
                                documentos = list(self.collection.find({}, {
                                    '_id': 1, 'tipo': 1, 'dados': 1, 'ordem': 1,
                                    'chave': 1, 'livro_id': 1, 'cliente_id': 1,
                                }, session=session))
                                antes = {doc['_id']: doc for doc in documentos}
                                restaurar(self.loja, documentos)
                                resultado = operacao()
                                depois = exportar(self.loja)
                                comandos = [
                                    InsertOne(doc) if chave not in antes else ReplaceOne({'_id': chave}, doc)
                                    for chave, doc in depois.items() if antes.get(chave) != doc
                                ]
                                comandos.extend(DeleteOne({'_id': chave}) for chave in antes.keys() - depois.keys())
                                if comandos:
                                    self.collection.bulk_write(comandos, ordered=True, session=session)
                                self._commit(session)
                                return resultado
                            except Exception:
                                if session.in_transaction:
                                    try:
                                        session.abort_transaction()
                                    except PyMongoError:
                                        pass
                                raise
                    except PyMongoError as erro:
                        if tentativa < 2 and (
                            erro.has_error_label('TransientTransactionError')
                            or isinstance(erro, DuplicateKeyError)
                        ):
                            sleep(0.025 * (tentativa + 1))
                            continue
                        raise BancoIndisponivel() from None
            finally:
                self._executando = False
