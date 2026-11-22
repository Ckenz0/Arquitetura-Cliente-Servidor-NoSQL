"""Documentação pública da API e execução no próprio servidor."""

from pathlib import Path
from urllib.parse import urlsplit
import re

import pytest
import yaml
from playwright.sync_api import expect

from server.app import create_app


@pytest.mark.parametrize('caminho', ['/docs', '/docs/'])
def test_documentacao_abre_sem_sessao_e_entrega_assets_locais(caminho):
    app = create_app()
    cliente = app.test_client()
    resposta = cliente.get(caminho, follow_redirects=True)
    assert resposta.status_code == 200
    assert resposta.mimetype == 'text/html'
    html = resposta.get_data(as_text=True)
    assert 'swagger-ui' in html
    assets = re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', html)
    assert assets
    for asset in assets:
        assert not urlsplit(asset).netloc
        recurso = cliente.get(asset)
        assert recurso.status_code == 200
        assert recurso.mimetype in {'text/css', 'text/javascript', 'application/javascript'}
    assert app.extensions['livraria'].dados.listar('clientes') == ()


def test_openapi_publico_preserva_contrato_e_aponta_para_servidor_atual():
    app = create_app()
    resposta = app.test_client().get('/openapi.json')
    assert resposta.status_code == 200
    assert resposta.is_json
    contrato = yaml.safe_load((Path(__file__).resolve().parents[1] / 'server/openapi.yaml').read_text(encoding='utf-8'))
    publicado = resposta.json
    assert publicado.pop('servers') == [{'url': '/', 'description': 'Servidor atual'}]
    contrato.pop('servers')
    assert publicado == contrato
    assert app.extensions['livraria'].dados.listar('clientes') == ()


def test_swagger_pode_criar_sessao_na_propria_origem():
    cliente = create_app().test_client()
    resposta = cliente.post('/api/sessoes', json={}, headers={'Origin': 'http://localhost'})
    assert resposta.status_code == 201
    assert resposta.json['tipo'] == 'Bearer'
    assert cliente.post('/api/sessoes', json={}, headers={'Origin': 'https://outro.example'}).status_code == 403


def test_origem_https_da_azure_funciona_atras_do_proxy(monkeypatch):
    monkeypatch.setenv('WEBSITE_HOSTNAME', 'entrelinhas-api.example.azurewebsites.net')
    app = create_app()
    app.config['APP_ENV'] = 'production'
    resposta = app.test_client().post('/api/sessoes', json={},
        base_url='http://entrelinhas-api.example.azurewebsites.net',
        headers={'Origin': 'https://entrelinhas-api.example.azurewebsites.net'})
    assert resposta.status_code == 201


@pytest.mark.interface
def test_swagger_carrega_contrato_e_executa_requisicao_no_mesmo_host(page, servidores):
    erros = []
    page.on('pageerror', lambda erro: erros.append(str(erro)))
    page.goto(servidores.api_url + '/docs')
    expect(page.locator('.swagger-ui .info .title')).to_contain_text('Entrelinhas')
    operacao = page.locator('#operations-default-criar_sessao_anonima')
    operacao.locator('.opblock-summary').click()
    operacao.get_by_role('button', name='Try it out', exact=True).click()
    with page.expect_response(lambda resposta: resposta.url == servidores.api_url + '/api/sessoes' and resposta.request.method == 'POST') as resultado:
        operacao.get_by_role('button', name='Execute', exact=True).click()
    assert resultado.value.status == 201
    assert resultado.value.json()['tipo'] == 'Bearer'
    assert not erros
