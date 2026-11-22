"""Configuração externa; segredos pertencem somente ao servidor."""

import os
import secrets
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def configuracao(overrides=None):
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    ambiente = (overrides or {}).get('APP_ENV', os.environ.get('APP_ENV', 'development'))
    producao = ambiente == 'production'
    chave = os.environ.get('SECRET_KEY', '')
    origens = os.environ.get('ALLOWED_ORIGINS', '')
    config = {
        'APP_ENV': ambiente,
        'SECRET_KEY': chave or (None if producao else secrets.token_hex(32)),
        'ALLOWED_ORIGINS': origens or (() if producao else (
            'http://127.0.0.1:8080', 'http://localhost:8080',
        )),
        'SESSION_TOKEN_MAX_AGE': 86400,
        'MAX_CONTENT_LENGTH': 1024 * 1024,
        'STORAGE_BACKEND': os.environ.get('STORAGE_BACKEND', 'mongodb'),
        'MONGODB_URI': os.environ.get('MONGODB_URI', '' if producao else
            'mongodb://127.0.0.1:27018/?replicaSet=rs0&directConnection=true'),
        'MONGODB_DATABASE': os.environ.get('MONGODB_DATABASE', 'entrelinhas'),
        'MONGODB_COLLECTION': os.environ.get('MONGODB_COLLECTION', 'livraria'),
    }
    config.update(overrides or {})
    producao = config['APP_ENV'] == 'production'
    if producao and (not isinstance(config['SECRET_KEY'], str) or len(config['SECRET_KEY']) < 32):
        raise ValueError('Produção exige SECRET_KEY estável com pelo menos 32 caracteres.')
    origens = config['ALLOWED_ORIGINS']
    if isinstance(origens, str):
        origens = [origem.strip() for origem in origens.split(',') if origem.strip()]
    if not origens:
        raise ValueError('Informe ALLOWED_ORIGINS explicitamente.')
    for origem in origens:
        url = urlsplit(origem)
        if (url.scheme not in {'http', 'https'} or not url.netloc or url.path
                or url.query or url.fragment or url.username or url.password):
            raise ValueError('ALLOWED_ORIGINS aceita origens exatas, sem caminho ou curingas.')
        if '*' in origem:
            raise ValueError('Não use curingas em ALLOWED_ORIGINS.')
    config['ALLOWED_ORIGINS'] = tuple(origens)
    if config['STORAGE_BACKEND'] not in {'memory', 'mongodb'}:
        raise ValueError('STORAGE_BACKEND deve ser mongodb ou memory.')
    if producao and config['STORAGE_BACKEND'] != 'mongodb':
        raise ValueError('Produção exige armazenamento MongoDB persistente.')
    if config['STORAGE_BACKEND'] == 'mongodb':
        uri = config['MONGODB_URI']
        if not isinstance(uri, str) or not uri.startswith(('mongodb://', 'mongodb+srv://')):
            raise ValueError('Informe MONGODB_URI válida apenas no servidor.')
        for campo in ('MONGODB_DATABASE', 'MONGODB_COLLECTION'):
            if not isinstance(config[campo], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', config[campo]):
                raise ValueError(f'{campo} deve conter apenas letras, números, hífen ou sublinhado (1–63).')
    return config
