# Clube do Valor — Pipeline dbt

Projeto dbt para carregar transações e clientes em DuckDB, aplicar as transformações e validar a qualidade dos dados.

## Pré-requisito

- Docker, para garantir o mesmo ambiente em qualquer máquina.

## Estrutura

```text
.
├── Dockerfile
├── dbt_project.yml
├── .dbt/profiles.yml        # conexão local com DuckDB
├── seeds/                   # CSVs de entrada versionados
├── models/
│   ├── staging/             # padronização, tipos e filtros
│   ├── intermediate/        # regras intermediárias
│   └── marts/               # fato, dimensão e portfólio
├── macros/                  # lógica SQL reutilizável
└── tests/                   # testes singulares
```

No DuckDB, os objetos ficam organizados por schemas de camada. No dbt Docs, as mesmas camadas aparecem na aba **Group**:

| Camada | Conteúdo |
| --- | --- |
| `01_RAW` | Arquivos de origem carregados: `clients` e `transactions`. |
| `02_STG` | Views de dados preparados: `stg_clients` e `stg_transactions`. |
| `03_INT` | View de transações enriquecidas: `int_transactions`. |
| `04_MART` | Tabelas de consumo: `dim_clients`, `fact_transactions` e `mart_client_portfolio`. |

## Executar com Docker

Na raiz do projeto, construa a imagem:

```bash
docker build -t clube-valor-dbt .
```

Entre no contêiner montando a pasta local `data/`:

```bash
docker run --rm -it \
  --name clube-valor-dbt \
  --publish 8080:8080 \
  --mount type=bind,src="$PWD/data",dst=/app/data \
  clube-valor-dbt bash
```

Dentro do container, execute:

```bash
dbt seed
dbt run
dbt test
```

O banco DuckDB é salvo localmente em `data/clube_valor.duckdb`, pois essa pasta está montada no contêiner. Assim, ele pode ser aberto pela extensão DuckDB do VS Code após a execução. Antes de rodar o pipeline, desconecte o banco no painel da extensão DuckDB (ou feche o VS Code); não basta fechar a aba. O DuckDB permite apenas um processo escritor por arquivo e uma conexão ativa pode causar erro de *lock*.

Após executar `dbt seed` e `dbt run`, atualize a árvore da extensão DuckDB para visualizar os quatro schemas. Se o banco já existia antes dessa organização, os objetos antigos em `main` podem permanecer visíveis; eles não são usados pelo pipeline atual.

O `dbt test` deve retornar código diferente de zero: os CSVs contêm problemas intencionais, como identificadores de cliente duplicados, cidade ausente e posições líquidas negativas. Esse resultado confirma que os testes estão detectando os problemas; os dados não devem ser corrigidos manualmente.

Para visualizar a documentação gerada no navegador:

```bash
dbt docs generate
dbt docs serve --host 0.0.0.0 --port 8080
```

Abra `http://localhost:8080`.

Para sair:

```bash
exit
```

