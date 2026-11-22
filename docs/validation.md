# Validação

Ambiente: Python 3.12, MongoDB 7.0 com replica set de um nó e navegador Chromium.
A suíte completa executou 210 testes com sucesso, incluindo integração com banco
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
