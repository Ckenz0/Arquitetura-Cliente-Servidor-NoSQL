# Persistência da livraria

## Organização documental

A coleção `livraria` contém documentos independentes com `_id`, `tipo` e `dados`.
O `_id` combina tipo e identificador de negócio, como `livros:1984`.

| Tipo | Conteúdo persistido |
| --- | --- |
| `livros` | Catálogo, estoque, códigos, localização e avaliações iniciais |
| `clientes` | Preferências, desejos, compras, pontos, cupons e notificações |
| `reservas` | Cliente, livro, prazo, embrulho e status |
| `avaliacoes` | Livro, cliente, nota, comentário e data |
| `acompanhamentos` | Leitores que aguardam reposição de um livro |
| `horarios` | Horário do livreiro e cliente agendado |
| `eventos` | Agenda, capacidade, inscritos e lembretes enviados |
| `clubes` | Membros e opiniões publicadas |
| `fila` | Ordem dos clientes na fila virtual |
| `loja` | Horário de funcionamento e lotação |
| `migracoes` | Versões aplicadas e data da carga inicial |

Conjuntos do domínio são convertidos em listas BSON e restaurados ao carregar
a transação. Pontos e recomendações continuam sendo calculados pelas regras
existentes, a partir das compras e preferências persistidas.

## Consistência

`MongoStore` abre uma sessão e uma transação por operação externa do serviço.
Chamadas internas compartilham essa transação. Os documentos são lidos do banco,
convertidos para os repositórios de trabalho e comparados ao final. Somente as
inclusões, alterações e exclusões são enviadas ao banco.

Uma reserva e sua baixa de estoque são confirmadas juntas; um cancelamento
e a devolução do exemplar também. Exceções abortam a operação. A transação protege
operações de instâncias diferentes, além do bloqueio de threads de cada processo.

Conflitos transitórios repetem a transação até três vezes. Se a confirmação do
commit for incerta, somente a confirmação é repetida, sem refazer a reserva.
Após falha de comunicação, consulte o estado antes de tentar uma mutação novamente.
A API retorna 503 sem expor detalhes da URI ou credenciais.

A coleção é única e **não particionada** porque o Cosmos DB for MongoDB baseado
em RU não suporta transações entre coleções ou partições. Consulte a
[documentação de transações da Microsoft](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/use-multi-document-transactions).

## Migrações

```powershell
.venv\Scripts\python.exe -m server.migrate
```

A versão 1 cadastra 12 livros e os dados iniciais de loja, agenda e comunidade.
O marcador `migracoes:1` é gravado na mesma transação. Reiniciar ou executar o
comando novamente preserva o estoque, os IDs, as datas e os dados de clientes.
Se a migração falhar, nenhuma parte da carga é confirmada.

Os dados demonstrativos do projeto anterior eram voláteis. Não existe um banco
legado do qual recuperar alterações de processos já encerrados. Esta migração
materializa a carga inicial e passa a persistir todas as operações seguintes.
Os preços e códigos do catálogo são ilustrativos.

Para consultar livros diretamente, use uma conexão autenticada do `mongosh`:

```javascript
use entrelinhas
db.livraria.countDocuments({tipo: 'livros'})
db.livraria.find({tipo: 'livros'}, {_id: 0, dados: 1})
db.livraria.find({tipo: 'migracoes'})
```

## Limites operacionais

O servidor MongoDB local precisa ser um replica set. O Compose prepara um nó
único para desenvolvimento e testes; isso não fornece redundância de produção.
A implantação Azure usa Cosmos DB for MongoDB 7.0, baseado em RU,
com coleção não particionada.

O Cosmos limita a duração de uma transação a cinco segundos. Ler todos os
documentos por operação simplifica a preservação das regras do MVP, mas aumenta
o consumo de RU e a duração das operações conforme o banco cresce. Fila, compras
e opiniões também exigem limites de retenção e paginação para crescer com segurança.
O modelo não foi dimensionado para alto volume ou coleções particionadas.

A dependência PyMongo é limitada à série 4.20, validada com Cosmos DB for MongoDB
7.0 e com o MongoDB 7.0 local. Aguarde a propagação da versão do Cosmos antes de
iniciar a API; o endpoint precisa oferecer um protocolo compatível. Consulte a
[tabela de compatibilidade do driver](https://www.mongodb.com/docs/drivers/compatibility/?driver-language=python&python-driver-framework=pymongo).
