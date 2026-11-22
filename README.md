# Entrelinhas

Livraria com catálogo de 12 livros, reservas, avaliações, fidelidade e comunidade.
Frontend independente em HTML, CSS e JavaScript, API Flask e persistência completa
em Azure Cosmos DB for MongoDB.

[Abrir a livraria](https://jolly-smoke-081cd9510.3.azurestaticapps.net) ·
[API](https://entrelinhas-nosql-api-ckenz0.azurewebsites.net) ·
[Documentação interativa](https://entrelinhas-nosql-api-ckenz0.azurewebsites.net/docs) ·
[Health check](https://entrelinhas-nosql-api-ckenz0.azurewebsites.net/api/health)

## Arquitetura

```text
Navegador ⇄ HTTP/JSON + Bearer ⇄ API Flask
                                  ↓
                          Serviços e domínio
                                  ↓
                        Unidade transacional PyMongo
                                  ↓
                        Cosmos DB for MongoDB
```

O cliente está em `client/`, a API em `server/` e o contrato HTTP em
[server/openapi.yaml](server/openapi.yaml). A separação entre cliente e servidor
permite publicar cada parte em um serviço independente.

A documentação interativa fica em `/docs`, e o contrato JSON em `/openapi.json`.
Para testar operações autenticadas no Swagger UI, execute `POST /api/sessoes`,
copie o campo `token` da resposta e informe-o em **Authorize**.

O banco guarda catálogo, estoque, clientes, reservas, avaliações, preferências,
lista de desejos, compras, pontos, cupons, notificações, fila, agendamentos,
eventos, inscrições, clubes e opiniões. Reiniciar a API preserva esses dados.
Consulte o [modelo de persistência](docs/persistence.md).

## Executar com Docker

```powershell
docker compose up --build -d
```

Abra `http://127.0.0.1:8080`. A API fica em `http://127.0.0.1:5000` e o MongoDB
local na porta `27018`. A carga inicial é automática e idempotente. O volume
`mongo-data` mantém os dados quando os contêineres são recriados.

```powershell
docker compose down
```

O comando acima preserva o volume. Remover o volume elimina o banco local.
A chave padrão do Compose serve apenas para desenvolvimento; configure uma
`SECRET_KEY` própria e estável no ambiente de produção.

## Executar com Python

Use Python 3.12 e um MongoDB com replica set habilitado:

```powershell
docker compose up -d --wait mongo
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Defina uma `SECRET_KEY` estável no `.env`. Depois:

```powershell
.venv\Scripts\python.exe -m server.migrate
.venv\Scripts\python.exe -m server.app
```

Em outro terminal:

```powershell
.venv\Scripts\python.exe -m http.server 8080 --bind 127.0.0.1 --directory client
```

As variáveis `MONGODB_URI`, `MONGODB_DATABASE` e `MONGODB_COLLECTION` são lidas
apenas pelo servidor. A URI do Cosmos DB nunca deve ir para `client/config.js`.
As migrações também são executadas ao iniciar a API; repeti-las não redefine
estoque, reservas ou calendário.

## Validação

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27018/?replicaSet=rs0&directConnection=true'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m openapi_spec_validator server/openapi.yaml
```

Os testes de integração usam um banco temporário independente por cenário.
Sem `TEST_MONGODB_URI`, esses testes são pulados explicitamente. A regressão de
domínio usa memória por configuração exclusiva dos testes; a aplicação usa MongoDB
por padrão e exige armazenamento persistente em produção.

Para testes de interface, use Chrome/Edge instalado ou execute
`.venv\Scripts\python.exe -m playwright install chromium`.
As [evidências de validação](docs/validation.md) descrevem a cobertura.

## Publicação

O [guia de deploy](docs/deploy.md) explica a infraestrutura Azure, configuração
segura e publicação independente do frontend e da API. A infraestrutura declarativa
está em [infrastructure/azure.json](infrastructure/azure.json).

Os workflows do GitHub validam API, contrato, persistência, concorrência e interface.
A publicação automática depende da configuração Azure descrita no guia.

## Limites

A identidade é anônima, sem cadastro ou login, e seu token dura 24 horas.
Uma `SECRET_KEY` estável mantém o token válido após reiniciar a API, dentro desse
prazo. Abrir uma nova sessão cria outra identidade; persistência não adiciona
recuperação de conta. Não há pagamentos, caixa ou notificações externas.

A implementação atende uma livraria de pequeno porte: cada operação lê os
documentos do banco e grava apenas os alterados numa transação curta. O Cosmos DB
for MongoDB exige uma coleção não particionada nesse modelo e limita transações
a cinco segundos. Evolução para alto volume exige consultas e agregados mais
específicos; veja [persistência](docs/persistence.md#limites-operacionais).
