"""Aplica migrações idempotentes e verifica o catálogo do banco configurado."""

from server.config import configuracao
from server.persistence.factory import criar_livraria_mongo


def main():
    config = configuracao()
    if config['STORAGE_BACKEND'] != 'mongodb':
        raise SystemExit('A migração exige STORAGE_BACKEND=mongodb.')
    try:
        loja, store = criar_livraria_mongo(config)
        try:
            quantidade = len(loja.buscar())
            if quantidade < 10:
                raise SystemExit('O catálogo deve conter pelo menos dez livros.')
            print(f'Migrações aplicadas. Catálogo persistente: {quantidade} livros.')
        finally:
            store.client.close()
    except RuntimeError as erro:
        raise SystemExit(str(erro)) from None


if __name__ == '__main__':
    main()
