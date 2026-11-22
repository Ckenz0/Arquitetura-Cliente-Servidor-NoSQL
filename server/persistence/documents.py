"""Conversão explícita entre o domínio e documentos BSON por entidade."""

from copy import deepcopy

from server.repositories import RepositorioEstado, RepositorioLivros


def _bson(valor):
    if isinstance(valor, set):
        return sorted(valor)
    if isinstance(valor, dict):
        return {chave: _bson(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_bson(item) for item in valor]
    return valor


def exportar(loja):
    documentos = {}

    def adicionar(identificador, tipo, dados, **campos):
        documentos[identificador] = {
            '_id': identificador, 'tipo': tipo, 'dados': _bson(dados), **campos,
        }

    for ordem, livro in enumerate(loja.repositorio.todos()):
        adicionar(f'livros:{livro["id"]}', 'livros', livro, ordem=ordem)
    estado = loja.dados
    for tipo, colecao in estado._colecoes.items():
        for identificador, valor in colecao.items():
            adicionar(f'{tipo}:{identificador}', tipo, valor, chave=identificador)
    for (livro, cliente), avaliacao in estado._avaliacoes.items():
        adicionar(f'avaliacoes:{livro}:{cliente}', 'avaliacoes', avaliacao,
                  livro_id=livro, cliente_id=cliente)
    adicionar('loja', 'loja', estado._loja)
    adicionar('fila', 'fila', estado._fila)
    for versao, dados in getattr(estado, '_migracoes', {}).items():
        adicionar(f'migracoes:{versao}', 'migracoes', dados, chave=versao)
    return deepcopy(documentos)


def restaurar(loja, documentos):
    estado = RepositorioEstado()
    estado.lock = loja._lock
    estado._migracoes = {}
    livros = []
    for documento in documentos:
        tipo, dados = documento['tipo'], deepcopy(documento['dados'])
        if tipo == 'livros':
            livros.append((documento['ordem'], dados))
        elif tipo in estado._colecoes:
            if tipo == 'acompanhamentos':
                dados = set(dados)
            elif tipo == 'eventos':
                for campo in ('inscritos', 'avisados'):
                    dados[campo] = set(dados[campo])
            elif tipo == 'clubes':
                dados['membros'] = set(dados['membros'])
            estado._colecoes[tipo][documento['chave']] = dados
        elif tipo == 'avaliacoes':
            estado._avaliacoes[(documento['livro_id'], documento['cliente_id'])] = dados
        elif tipo == 'fila':
            estado._fila = dados
        elif tipo == 'loja':
            estado._loja = dados
        elif tipo == 'migracoes':
            estado._migracoes[documento['chave']] = dados
        else:
            raise ValueError('Tipo de documento não suportado por esta versão.')
    loja.dados = estado
    loja.repositorio = RepositorioLivros([livro for _, livro in sorted(livros)])
