# Plataforma de Dados de Cinema — Especificação do Projeto

Plataforma autoral de Engenharia de Dados, Nuvem e IA para portfólio profissional. Cruza dados quantitativos do mercado de cinema (bilheteria, orçamento, ROI, elenco, disponibilidade em streaming) com dados qualitativos (reviews e percepção do público), consultáveis em linguagem natural.

Fontes: API do TMDB (oficial, REST) e JustWatch (não oficial, GraphQL via `simple-justwatch-python-api`), mercado BR.

## 1. Repositórios

| Repositório | Papel |
|---|---|
| `data-platform-core` (**este repositório**) | Plataforma compartilhada: infraestrutura base, governança e contratos de dados de todos os domínios. Será reutilizado por futuros projetos de portfólio. |
| `cinema-intelligence` | Domínio cinema: `pipeline/` (ingestão e ETL) e `agent/` (aplicação de IA). |

Critério da divisão: ciclo de vida e reuso. O Core serve vários projetos; pipeline e agente de cinema evoluem juntos e ficam no mesmo repositório, com workflows de CI separados por pasta.

## 2. Contratos de dados orientados a metadados

O **Glue Data Catalog é a fonte da verdade publicada**, e o Core é o **único escritor** do catálogo. Os produtores não importam código do Core.

```
data-platform-core                              cinema-intelligence (ETL)
 contracts/ (StructType)                         lê o schema do catálogo em runtime
      │                                          spark.table("cinema_silver_dev.x").schema
      ▼                                                    │
 check de compatibilidade (CI) ──► job Glue de DDL ──►  Glue Catalog  ◄── valida o DataFrame
                                  (PySpark)                │             válido   → escreve no S3
                                                           │             inválido → quarentena
```

- **Contrato:** um `StructType` por tabela, definido somente no Core. Cada campo carrega `metadata` (descrição, unidade, PII). Cada tabela declara versão, camada, formato, particionamento e dono.
- **Registro no catálogo:** um job PySpark no AWS Glue cria e evolui as tabelas a partir dos contratos (`writeTo(...).using("iceberg").create()`, `CREATE TABLE ... TBLPROPERTIES`, `ALTER TABLE ... ADD COLUMN`). O mesmo motor que escreve os dados gera o DDL, então não há tradução manual de tipos.
- **Compatibilidade:** o CI do Core compara cada contrato alterado com a tabela publicada.
  - Mudança aditiva (coluna nova nullable): liberada, release minor.
  - Breaking change (remover campo, mudar tipo, tornar obrigatório): bloqueada; exige tabela nova (`<tabela>_v2`) e release major.
- **Views:** as views do gold (`vw_*`) também são objetos do catálogo, então são definidas e publicadas pelo Core, versionadas junto com os contratos.
- **Integridade:** Iceberg e Athena não aplicam `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE` nem `CHECK`. Unicidade é garantida pelo `MERGE`, tipos e nulidade pelo contrato, e regras de domínio (ex.: nota entre 0 e 10) por validações no silver, com reprovados em `quarantine/`.
- **Rastreabilidade:** o Glue versiona as tabelas a cada atualização; as releases do Core são tags semver no git.
- **Validação no produtor:** o ETL lê o schema do catálogo, valida antes de escrever e envia registros inválidos para `quarantine/`. Erros de contrato aparecem em runtime, compensados por teste de integração no CI do produtor (role de leitura do catálogo via OIDC).
- **Evolução futura:** se houver muitos produtores e for necessária checagem em build time, distribuir os contratos como pacote Python versionado.

## 3. Data Lake (S3, arquitetura medallion)

Ambiente inicial: `dev`. A estrutura é preparada para `prd`.

```
s3://<prefixo>-lake-<env>/
  bronze/<dominio>/<tabela>/dt=AAAA-MM-DD/      JSON imutável, como a API devolveu
  silver/<dominio>/<tabela>/...                 Parquet tipado, validado, deduplicado
  gold/<dominio>/<tabela>/...                   Iceberg, modelo dimensional (views vw_* não geram arquivos)
  quarantine/<dominio>/<tabela>/dt=.../         registros reprovados no contrato
```

| Camada | Formato | Catálogo | Permissão do produtor no Glue |
|---|---|---|---|
| bronze | JSON com envelope (`ingested_at`, `source`, `endpoint`, `payload`) | Tabela Hive com partition projection | Nenhuma |
| silver | Parquet | Tabela Hive com partition projection | Nenhuma |
| gold | Apache Iceberg | Tabela Iceberg no Glue | `glue:UpdateTable` restrito às tabelas do domínio (commits do Iceberg atualizam o ponteiro de metadata) |

- O bronze nunca é validado contra o contrato e nunca é sobrescrito; isso garante o reprocessamento.
- No gold, a proteção do schema vem do Iceberg: escritas com schema incompatível falham, porque a evolução de schema na escrita fica desabilitada.
- Papel de cada camada: bronze guarda o que a fonte mandou; silver guarda o dado correto, organizado por entidade da fonte (ex.: `tmdb_filmes`, `justwatch_ofertas`, `correspondencia`); gold responde perguntas de negócio (star schema + views).
- Views no gold (`vw_*`): junções e consultas recorrentes prontas para Power BI e Text-to-SQL. Começam como views do Athena (legíveis só pelo Athena, não pelo Spark) e só viram tabela materializada (`mart_*`) quando custo ou latência justificarem.
- Glue Database por domínio, camada e ambiente: `<dominio>_<camada>_<env>` (ex.: `cinema_bronze_dev`, `cinema_silver_dev`, `cinema_gold_dev`). A fronteira de permissão é o database: a role do agente recebe `table/cinema_gold_dev/*` e uma tabela nova herda o acesso certo sem depender do nome. Nomes com underscore, nunca hífen (o Athena exigiria aspas).

## 4. Infraestrutura como código (Terraform)

**Responsabilidades do Core:**
- bootstrap do bucket de estado (aplicado uma vez); backend S3 com `use_lockfile`, sem DynamoDB. Depois de criado, o estado do próprio bootstrap foi migrado para o bucket. Um bucket de estado para todos os repositórios e ambientes, separados por key: `<repositorio>/<bootstrap|env>/terraform.tfstate`;
- buckets do data lake, de artefatos (scripts dos jobs Glue) e de resultados do Athena;
- Glue Databases por domínio e camada;
- workgroup do Athena com limite de bytes lidos por consulta;
- provedor OIDC do GitHub e roles:
  - `core-deploy`: único com permissão de criar e alterar tabelas;
  - `<dominio>-pipeline`: escreve só em `*/<dominio>/*`;
  - `<dominio>-agent`: somente leitura na camada gold do domínio;
- job Glue de DDL;
- AWS Budgets com alerta de custo (até a ativação dos recursos avançados, a proteção é o limite de gastos do AWS Settings; ver §9).

**Responsabilidades de cada projeto:** a própria computação (Lambdas, jobs Glue de ETL, Step Functions, API).

**Integração:** o Core publica suas saídas no SSM Parameter Store (`/platform/<env>/...`), e os projetos leem de lá. Nada de `terraform_remote_state`, para manter o acoplamento baixo.

## 5. Estrutura do repositório Core

```
data-platform-core/
├── infra/                     # root principal: main.tf, providers.tf, variables.tf, <env>.tfvars
│   ├── bootstrap/             # root separado: bucket de estado do Terraform
│   └── modules/               # lake, catalog, iam, glue_job, budget...
├── src/platform_core/
│   ├── contracts/cinema/      # StructType por tabela + metadados
│   ├── ddl/                   # contrato → DDL Spark (create / evolução)
│   └── compat/                # checagem de compatibilidade de schemas
├── jobs/                      # entrypoints dos jobs Glue (ex.: deploy_contracts.py)
├── tests/                     # pytest + SparkSession local com catálogo Iceberg local
└── .github/workflows/
```

## 6. CI/CD (GitHub Actions)

Autenticação na AWS via OIDC, sem chaves de longa duração.

**Pull request:**
- `ruff`;
- `pytest` (contratos, DDL e compatibilidade com Spark local);
- check de compatibilidade dos contratos;
- `terraform fmt`, `validate` e `plan`.

**Merge na main:**
- `terraform apply`;
- upload dos scripts para o bucket de artefatos;
- execução do job Glue de DDL;
- tag semver.

## 7. Domínio cinema (`cinema-intelligence`)

**Pipeline**
- **Orquestração:** EventBridge Scheduler + Step Functions. O GitHub Actions fica só com CI/CD.
- **Extração:** Lambdas em Python (`httpx`) para TMDB e JustWatch, gravando no bronze.
  - Throttling e retry com backoff exponencial.
  - O discover do TMDB é particionado por ano (limite de 500 páginas por consulta), com Map state no Step Functions.
  - Spark não é usado para chamadas HTTP (anti-padrão).
- **Transformação:** jobs PySpark no AWS Glue (versão 5.x).
  - bronze → silver: achatamento, tipagem, deduplicação, validação de contrato.
  - silver → gold: modelo dimensional com `MERGE` no Iceberg.
- **Matching TMDB ↔ JustWatch:** primeiro por `tmdb_id`/`imdb_id`; fallback por título + ano (±1) + similaridade ≥ 0,85. O resultado fica numa tabela de correspondência com status `CONFIRMADO` / `AMBIGUO` / `NAO_ENCONTRADO`.
- **Modelo gold (star schema):**
  - `fact_filmes`: uma linha por filme;
  - `fact_ofertas_streaming` como **snapshot periódico** (filme × plataforma × país × data da coleta), o que permite responder "quando saiu do catálogo". A data da coleta faz parte da chave; a precisão da saída é limitada pela frequência de coleta;
  - dimensões: filme, data, gênero, estúdio, pessoa, plataforma, país;
  - pontes (`ponte_filme_genero`, `ponte_filme_estudio`, `ponte_filme_elenco`) para os relacionamentos N:N. Somas de métricas do filme não passam pela ponte (fan-out); filtros por gênero usam `EXISTS`;
  - métricas que dependem da data de coleta (ex.: quantidade de plataformas) ficam em views, não na `fact_filmes`;
  - views candidatas: `vw_filme_desempenho`, `vw_janelas_catalogo` (entradas e saídas do catálogo com `LAG`).
- **Testes:** pytest + SparkSession local + chispa, com fixtures das APIs.

**Agente de IA**
- **API:** FastAPI em AWS Lambda + API Gateway. Avaliar Function URL com streaming por causa do timeout de 29 s.
- **Front-end:** AWS Amplify.
- **Text-to-SQL:** lê os schemas do Glue Catalog e consulta o Athena com a role somente leitura do gold e o limite de bytes do workgroup. A segurança é garantida pela infraestrutura, não apenas por validação do SQL.
- **RAG:** embeddings dos reviews gerados no pipeline, via API de embeddings do provedor; o mesmo modelo é usado na consulta.
- **Orquestração do agente:** roteador que aciona SQL e RAG em paralelo e consolida a resposta.

**Fluxo de exemplo:** "Por que o filme novo do Homem-Aranha fez mais sucesso de bilheteria que o da Wanda?"
1. Text-to-SQL busca orçamento, bilheteria e ROI dos dois filmes.
2. O RAG busca opiniões sobre roteiro, atuação e efeitos.
3. A LLM sintetiza números e contexto qualitativo.

## 8. Ordem de execução

1. **Core:** Terraform base (bootstrap, lake, catálogo, IAM, budget), primeiro contrato, job de DDL e CI.
2. **Cinema, pipeline:** extração → bronze → silver → gold, com orquestração.
3. **Cinema, agente:** Text-to-SQL, RAG, API e front.
4. **Entrega da PUC (por último):** Power BI conectado ao Athena (conector nativo) e documentação acadêmica.

## 9. Decisões em aberto

- **Banco vetorial:** LanceDB sobre S3, pgvector (Neon/Supabase) ou Amazon S3 Vectors (conferir disponibilidade na região).
- **LLM:** Gemini ou Groq, em versões atuais (Gemini 1.5 Flash foi descontinuado).
- **Orquestração do agente:** LangGraph ou function calling direto.
- **Chaves do gold:** chave natural (`tmdb_id`) ou hash determinístico da chave natural (`xxhash64`); autoincremento não escala em processamento distribuído.

Decididas:
- Prefixo dos buckets `lilith-fern` (lake: `lilith-fern-lake-<env>`; estado: `lilith-fern-tfstate-<conta>`).
- Ambientes separados por `<env>.tfvars` + backend parcial, com bucket, key e região passados no `terraform init` (no CI, por cada workflow).
- Região `us-east-2`. A conta está na nova experiência da AWS (projeto `portifolio-lilith`, dono: Builder ID), cujas SCPs liberam na `us-east-1` só serviços globais (IAM, STS, Budgets) e bloqueiam o resto fora da região do projeto.
- Login local: `aws login --profile portifolio-dev` (credenciais temporárias, role `AccountFullAccessRole`).
- **OIDC do GitHub bloqueado** pela SCP `DenyIAMRestrictedActions` (`iam:*Provider*`), tanto no plano gratuito quanto no pago. Decisão: aplicar o Terraform localmente até a etapa de CI; ao chegar nela, fazer o upgrade e ativar os recursos avançados (irreversível; remove o limite de gastos, substituído por AWS Budgets com ação automática). Access keys no CI estão descartadas.
- Plano gratuito também bloqueia gravar objetos direto em `GLACIER`/`DEEP_ARCHIVE` (afeta lifecycle do bronze).

## 10. Diretrizes de trabalho com o Claude

Atuar como Engenheiro de Dados Sênior e Arquiteto de Nuvem:

- Código limpo, modular e tipado em Python, PySpark e Terraform, seguindo PEP 8 e desacoplamento.
- Explicar decisões arquiteturais e trade-offs para que eu consiga defender a solução em entrevistas.
- Rigor nos contratos de dados (StructType) e na integração com os serviços da AWS.
- Priorizar ferramentas usadas no mercado.
- Construir de forma incremental, explicando os conceitos de engenharia de dados envolvidos.
- Formato de curso: explicar o conceito antes, escrever junto e passar atividades (eu escrevo, o Claude revisa). Nada de criar arquivos em lote.

## 11. Onde paramos

**Concluído (Core, etapa 1 do §8):**
- Aulas 1–7: bloco `terraform {}`, providers, variáveis e validação, módulos, backend S3, bootstrap aplicado e com estado migrado para o S3, módulo `lake` aplicado (`lilith-fern-lake-dev`, sem versionamento).

**Em andamento: Aula 8, Glue Data Catalog**
- Módulo `infra/modules/catalog` escrito (`for_each` sobre `map(string)` nome → `location_uri`), chamado no root com `setproduct(domains, layers)`.
- Pendente: corrigir `"s3//"` → `"s3://"` no `glue_databases` do `infra/main.tf` (Atividade 8.1); rodar `plan` (esperado: 3 databases `cinema_{bronze,silver,gold}_dev`, conferir `location_uri`) e `apply`; commitar `infra/main.tf`, `infra/modules/catalog/` e `project.md`.

**Próximos passos do Core:** buckets de artefatos e de resultados do Athena; workgroup do Athena; roles de IAM; SSM Parameter Store; limite de gastos/Budgets; primeiro contrato (`StructType`) e job de DDL; CI (com a ativação dos recursos avançados da conta).

**Lembretes de ambiente (Windows):**
- No PowerShell, flags com `=` e ponto precisam de `--` ou aspas (`--var-file=dev.tfvars`, `--out=dev.tfplan`).
- Antes de qualquer comando: `aws login --profile portifolio-dev` e `$env:AWS_PROFILE = "portifolio-dev"`.
- Ao trocar de root, conferir a key do backend em `.terraform/terraform.tfstate` (dois roots na mesma key leva o plan a destruir recursos do outro).

