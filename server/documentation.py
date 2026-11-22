"""Swagger UI público usando o contrato OpenAPI versionado da aplicação."""

from pathlib import Path

from flask import Blueprint, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
import yaml


def registrar_documentacao(app):
    contrato = yaml.safe_load(Path(__file__).with_name('openapi.yaml').read_text(encoding='utf-8'))
    contrato['servers'] = [{'url': '/', 'description': 'Servidor atual'}]
    blueprint = Blueprint('documentacao', __name__)

    @blueprint.get('/openapi.json')
    def openapi():
        return jsonify(contrato)

    app.register_blueprint(blueprint)
    app.register_blueprint(get_swaggerui_blueprint('/docs', '/openapi.json', config={
        'app_name': 'Entrelinhas — documentação da API',
        'deepLinking': True,
        'validatorUrl': None,
        'persistAuthorization': False,
    }))
