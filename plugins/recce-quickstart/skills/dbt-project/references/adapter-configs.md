# Warehouse Adapter Configurations

## Adapter Package Mapping

| Adapter Type | dbt Package | profiles.yml `type:` value |
|---|---|---|
| Snowflake | dbt-snowflake | snowflake |
| BigQuery | dbt-bigquery | bigquery |
| PostgreSQL | dbt-postgres | postgres |
| Databricks | dbt-databricks | databricks |
| Redshift | dbt-redshift | redshift |
| DuckDB | dbt-duckdb | duckdb |

## profiles.yml Examples

### Snowflake

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: TRANSFORMER
      warehouse: TRANSFORMING
      database: ANALYTICS
      schema: jaffle_shop
    ci:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: TRANSFORMER
      warehouse: TRANSFORMING
      database: CI_ANALYTICS
      schema: "pr_{{ env_var('PR_NUMBER', 'local') }}"
```

### BigQuery

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: my-project
      dataset: jaffle_shop
    ci:
      type: bigquery
      method: service-account
      project: my-project
      dataset: "ci_jaffle_shop_pr{{ env_var('PR_NUMBER', 'local') }}"
      keyfile_json: "{{ env_var('GOOGLE_APPLICATION_CREDENTIALS_JSON') }}"
```

### PostgreSQL

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: postgres
      host: "{{ env_var('POSTGRES_HOST') }}"
      user: "{{ env_var('POSTGRES_USER') }}"
      password: "{{ env_var('POSTGRES_PASSWORD') }}"
      dbname: "{{ env_var('POSTGRES_DATABASE') }}"
      port: 5432
      schema: jaffle_shop
```

### Databricks

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: databricks
      host: "{{ env_var('DATABRICKS_HOST') }}"
      token: "{{ env_var('DATABRICKS_TOKEN') }}"
      http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
      schema: jaffle_shop
```

### Redshift

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: redshift
      host: "{{ env_var('REDSHIFT_HOST') }}"
      user: "{{ env_var('REDSHIFT_USER') }}"
      password: "{{ env_var('REDSHIFT_PASSWORD') }}"
      dbname: "{{ env_var('REDSHIFT_DATABASE') }}"
      port: 5439
      schema: jaffle_shop
```

### DuckDB

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "target/jaffle_shop.duckdb"
      schema: main
```

## Detection Logic

To identify the adapter:
1. Read `profiles.yml` (project directory first, then `~/.dbt/profiles.yml`)
2. Find the active profile target
3. Extract the `type:` field value
4. Map to package name using the table above
