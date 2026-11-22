# Deploy na Azure

O frontend executa no Azure Static Web Apps; a API Flask executa no App Service
Linux e acessa o Cosmos DB for MongoDB 7.0. O navegador fala somente com a API,
por HTTPS/JSON, sem receber a conexão do banco.

## Recursos

Grupo de recursos: `livraria-entrelinhas-nosql`.

| Componente | Recurso | Região |
| --- | --- | --- |
| Frontend | `entrelinhas-nosql-front-ckenz0` | Central US |
| API | `entrelinhas-nosql-api-ckenz0` | Brazil South |
| Plano da API | `entrelinhas-nosql-plan` | Brazil South |
| Banco | `entrelinhas-nosql-ckenz0` | Brazil South |
| Identidade de CI | `entrelinhas-nosql-github` | Brazil South |

Os recursos são independentes da versão anterior da livraria.
O template usa Static Web Apps Free, App Service F1 e Cosmos com free tier
habilitado e uma coleção de 400 RU/s. A assinatura precisa ter o free tier
do Cosmos disponível; mudar essa configuração pode gerar cobrança.

Endereços atribuídos aos recursos:

- Frontend: <https://jolly-smoke-081cd9510.3.azurestaticapps.net>.
- API: <https://entrelinhas-nosql-api-ckenz0.azurewebsites.net>.
- Saúde da API e conexão do banco: <https://entrelinhas-nosql-api-ckenz0.azurewebsites.net/api/health>.
- Documentação interativa: <https://entrelinhas-nosql-api-ckenz0.azurewebsites.net/docs>.
- Contrato OpenAPI: <https://entrelinhas-nosql-api-ckenz0.azurewebsites.net/openapi.json>.

Consulte os domínios reais depois de provisionar; eles não devem ser derivados
do nome do recurso:

```powershell
az webapp show -g livraria-entrelinhas-nosql -n entrelinhas-nosql-api-ckenz0 --query defaultHostName -o tsv
az staticwebapp show -g livraria-entrelinhas-nosql -n entrelinhas-nosql-front-ckenz0 --query defaultHostname -o tsv
```

## Provisionamento

O template [infrastructure/azure.json](../infrastructure/azure.json) cria plano,
API, frontend, conta Cosmos, banco `entrelinhas` e coleção `livraria` sem shard key.
Também configura a API com a conexão do banco e a origem correta do frontend.
O parâmetro `secretKey` é `securestring` e não aparece nas saídas do deployment.

```powershell
az login
az provider register --namespace Microsoft.DocumentDB --wait
az group create --name livraria-entrelinhas-nosql --location brazilsouth
```

Prepare `.env.azure.parameters.json` localmente, usando uma chave aleatória estável
com pelo menos 32 caracteres. O padrão `.env.*` impede seu versionamento:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "secretKey": { "value": "SUBSTITUA_POR_UMA_CHAVE_ALEATORIA_E_ESTAVEL" }
  }
}
```

```powershell
az deployment group create --name entrelinhas-nosql-infra --resource-group livraria-entrelinhas-nosql --template-file infrastructure/azure.json --parameters '@.env.azure.parameters.json'
```

Preserve a mesma chave em novas aplicações do template. Confira que a conta
Cosmos esteja com protocolo 7.0 antes de iniciar a API. A criação ou atualização
da versão do serviço pode levar alguns minutos para se propagar. Não configure
shard key nessa coleção: as transações dependem de uma coleção não particionada.

## Configuração da API

| Variável | Valor |
| --- | --- |
| `APP_ENV` | `production` |
| `STORAGE_BACKEND` | `mongodb` |
| `MONGODB_URI` | Conexão autenticada do Cosmos, somente no backend |
| `MONGODB_DATABASE` | `entrelinhas` |
| `MONGODB_COLLECTION` | `livraria` |
| `SECRET_KEY` | Chave aleatória estável |
| `ALLOWED_ORIGINS` | Origem HTTPS exata do frontend, sem barra final |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

Runtime: Python 3.12 em Linux. Startup command: `bash startup.sh`.
O cliente PyMongo desativa `retryWrites` para a compatibilidade com Cosmos.
Mantenha TLS ativo e não use opções que desabilitem validação de certificados.

A inicialização da API aplica a migração idempotente. Se o banco estiver inacessível,
a inicialização falha explicitamente; não há fallback para memória.

O Swagger UI e seus arquivos são servidos pela própria API, sem CDN. O contrato
publicado usa a raiz do servidor atual para executar requisições. A origem da
própria API é permitida; no App Service, o HTTPS público é identificado pelo
`WEBSITE_HOSTNAME` fornecido pela Azure.

## GitHub Actions

Os workflows `backend.yml` e `frontend.yml` validam todos os pushes em `main` e
pull requests. O backend usa MongoDB real com replica set para as integrações;
o frontend também executa os testes de navegador. A publicação ocorre apenas em
`main`, após a validação e com `AZURE_DEPLOY_ENABLED=true`.

Configure em **Settings → Secrets and variables → Actions**:

| Tipo | Nome | Conteúdo |
| --- | --- | --- |
| Variable | `AZURE_DEPLOY_ENABLED` | `true` após configurar a infraestrutura |
| Variable | `AZURE_WEBAPP_NAME` | `entrelinhas-nosql-api-ckenz0` |
| Variable | `AZURE_API_BASE_URL` | Origem HTTPS real da API, sem `/api` |
| Secret | `AZURE_CLIENT_ID` | Client ID da identidade federada |
| Secret | `AZURE_TENANT_ID` | Tenant ID |
| Secret | `AZURE_SUBSCRIPTION_ID` | Assinatura |
| Secret | `AZURE_STATIC_WEB_APPS_API_TOKEN` | Token de publicação do Static Web App |

A identidade gerenciada `entrelinhas-nosql-github` usa federação OIDC com:

- Issuer: `https://token.actions.githubusercontent.com`.
- Audience: `api://AzureADTokenExchange`.
- Subject: `repo:Ckenz0@146033211/Arquitetura-Cliente-Servidor-NoSQL@1467822683:ref:refs/heads/main`.
- Role: `Website Contributor`, no escopo exclusivo da API desta versão.

Esse subject foi consultado na configuração OIDC do repositório, que usa IDs
imutáveis. Uma cópia do projeto precisa consultar seu próprio prefixo, e não
reutilizar o identificador deste repositório. OIDC não exige client secret.
A identidade de publicação é criada separadamente do template de infraestrutura.

## Publicação manual

```powershell
python scripts/package_backend.py --output dist/backend-azure.zip
az webapp deploy -g livraria-entrelinhas-nosql -n entrelinhas-nosql-api-ckenz0 --src-path dist/backend-azure.zip --type zip
python scripts/package_frontend.py --api-url https://entrelinhas-nosql-api-ckenz0.azurewebsites.net
```

O ZIP do backend inclui somente os arquivos de execução da API. O frontend
publica somente `dist/client/`, pelo workflow ou pelo Static Web Apps CLI.
`api_location` fica vazio porque o Flask é hospedado separadamente.

## Conferir a publicação

1. Verifique `/api/health`: resposta 200 com `{"status":"ok"}`.
2. Abra o frontend e confira catálogo, busca, detalhes e avaliações.
3. Faça uma reserva e salve preferências.
4. Reinicie somente a API, mantendo o banco e a chave.
5. Recarregue a mesma aba; confira a reserva, o estoque e as preferências.
6. Cancele a reserva e confirme a devolução de apenas um exemplar.
7. Confira em Network que assets vêm do Static Web Apps e chamadas `/api/`
   chegam ao App Service por HTTPS, sem erros de CORS.

Os registros do teste publicado ficam em [validation.md](validation.md).
Criar os recursos, por si só, não comprova o funcionamento da aplicação.

## Referências

- [Cosmos DB for MongoDB: transações e limitações](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/feature-support-70).
- [App Service: deploy ZIP e build remoto](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip).
- [App Service: GitHub Actions com identidade federada](https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions).
- [GitHub: subjects OIDC imutáveis](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims).
