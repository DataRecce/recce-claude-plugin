# Warehouse Secrets Configuration

## Snowflake

```
🔐 Required GitHub Secrets for Snowflake:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ SNOWFLAKE_ACCOUNT      │ Account identifier (xxx.region) │
│ SNOWFLAKE_USER         │ Username                        │
│ SNOWFLAKE_PASSWORD     │ Password                        │
├────────────────────────┼─────────────────────────────────┤
│ SNOWFLAKE_ROLE         │ (Optional) Role name            │
│ SNOWFLAKE_WAREHOUSE    │ (Optional) Warehouse name       │
│ SNOWFLAKE_DATABASE     │ (Optional) Database name        │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
  SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
  SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
```

## BigQuery

```
🔐 Required GitHub Secrets for BigQuery:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ GCP_SERVICE_ACCOUNT    │ Service Account JSON key        │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GCP_SERVICE_ACCOUNT }}

Alternative: Use Workload Identity Federation (recommended for production)
```

## PostgreSQL

```
🔐 Required GitHub Secrets for PostgreSQL:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ POSTGRES_HOST          │ Database host                   │
│ POSTGRES_USER          │ Username                        │
│ POSTGRES_PASSWORD      │ Password                        │
│ POSTGRES_DATABASE      │ Database name                   │
│ POSTGRES_PORT          │ (Optional) Port, default 5432   │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  POSTGRES_HOST: ${{ secrets.POSTGRES_HOST }}
  POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
  POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
  POSTGRES_DATABASE: ${{ secrets.POSTGRES_DATABASE }}
```

## Databricks

```
🔐 Required GitHub Secrets for Databricks:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ DATABRICKS_HOST        │ Workspace URL                   │
│ DATABRICKS_TOKEN       │ Personal Access Token           │
│ DATABRICKS_HTTP_PATH   │ SQL Warehouse HTTP path         │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
  DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_TOKEN }}
  DATABRICKS_HTTP_PATH: ${{ secrets.DATABRICKS_HTTP_PATH }}
```

## Redshift

```
🔐 Required GitHub Secrets for Redshift:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ REDSHIFT_HOST          │ Cluster endpoint                │
│ REDSHIFT_USER          │ Username                        │
│ REDSHIFT_PASSWORD      │ Password                        │
│ REDSHIFT_DATABASE      │ Database name                   │
│ REDSHIFT_PORT          │ (Optional) Port, default 5439   │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  REDSHIFT_HOST: ${{ secrets.REDSHIFT_HOST }}
  REDSHIFT_USER: ${{ secrets.REDSHIFT_USER }}
  REDSHIFT_PASSWORD: ${{ secrets.REDSHIFT_PASSWORD }}
  REDSHIFT_DATABASE: ${{ secrets.REDSHIFT_DATABASE }}
```

## DuckDB

```
🔐 GitHub Secrets for DuckDB:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ (No secrets required)  │ DuckDB is a local file database │
└────────────────────────┴─────────────────────────────────┘

DuckDB doesn't require external credentials.
```

## Setup Link

Configure secrets at:
https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions

Steps:
1. Click "New repository secret"
2. Add each secret from the appropriate table above
3. Ensure values match your profiles.yml configuration
