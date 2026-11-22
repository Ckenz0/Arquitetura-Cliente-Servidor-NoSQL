# Validação

Ambiente: Python 3.12, MongoDB 7.0 com replica set de um nó e navegador Chromium.
A suíte completa executou 216 testes com sucesso, incluindo integração com banco
real e os fluxos da interface em 1366 × 900 e 390 × 844.

## Cobertura

- Regras de negócio, API, identidade, CORS e contrato OpenAPI.
- Doze livros persistidos e consultados pela API.
- Dados de todas as funcionalidades disponíveis em uma nova instância da aplicação.
- Mesma sessão após reiniciar a API com chave estável.
- Carga inicial idempotente, sem redefinir estoque ou duplicar calendário.
- Reserva, cancelamento, avaliações e notificações sem gravações parciais.
- Concorrência entre instâncias para último exemplar, última vaga, agendamento
  e avaliação duplicada.
- Isolamento dos dados de clientes e resposta 503 sem credenciais em falhas do banco.
- Empacotamento sem segredos, arquivos locais, frontend no backend ou caches.
- Interface original consumindo a API persistente por HTTP em outra origem.
- Swagger UI em `/docs`, contrato público em `/openapi.json`, arquivos locais
  e execução de uma requisição pela própria documentação em navegador real.

## Reproduzir

```powershell
docker compose up -d --wait mongo
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27018/?replicaSet=rs0&directConnection=true'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m openapi_spec_validator server/openapi.yaml
docker compose config --quiet
```

As integrações usam nomes de banco temporários aleatórios e removem apenas os
bancos criados pelo próprio cenário. O MongoDB de produção não é usado pela suíte.

## Reinício do contêiner

O conjunto completo também foi executado com `docker compose up --build -d`.
Uma sessão HTTP reservou um livro e salvou preferências. Após `docker compose
restart api`, a mesma sessão recuperou os dados e cancelou a reserva, devolvendo
o exemplar ao estoque. O frontend e a API foram acessados nas portas 8080 e 5000.

## Aplicação publicada

Verificação realizada em 22 de novembro de 2026, usando Cosmos DB for MongoDB
7.0 e PyMongo 4.20.1 na composição de produção.

- [Frontend](https://jolly-smoke-081cd9510.3.azurestaticapps.net): catálogo de
  12 livros, busca funcional e nenhum erro JavaScript em desktop e celular.
- [API](https://entrelinhas-nosql-api-ckenz0.azurewebsites.net/api/health):
  health check respondeu 200, incluindo a conexão com o banco.
- Uma sessão HTTP salvou reserva com embrulho, preferências, desejos, avaliação,
  fila, agendamento, inscrição em evento, participação e opinião em clube.
- Após reiniciar o App Service, a mesma sessão recuperou todos esses dados,
  incluindo compras, pontos e cupom inicial. A baixa de estoque permaneceu.
- Cancelar duas vezes a mesma reserva devolveu apenas um exemplar ao estoque.
- Os registros públicos criados exclusivamente para essa verificação foram
  removidos ao final; o catálogo e o estoque foram preservados.

Publicação e validação automática concluídas com sucesso:

- [Workflow da API](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-NoSQL/actions/runs/45054811676).
- [Workflow do frontend](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-NoSQL/actions/runs/45054811560).

A documentação publicada também foi verificada em navegador real:
`/docs` carregou o Swagger UI e `/openapi.json` respondeu 200. Pela interface,
`POST /api/sessoes` respondeu 201 e, após autorizar com o token retornado,
`GET /api/livros` respondeu 200 com os 12 livros. Não ocorreram erros JavaScript.
A correção foi publicada pelo [workflow da API](https://github.com/Ckenz0/Arquitetura-Cliente-Servidor-NoSQL/actions/runs/45057777352).
