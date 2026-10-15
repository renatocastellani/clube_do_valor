FROM python:3.14-slim

WORKDIR /app

ENV DBT_PROFILES_DIR=/app/.dbt \
    DBT_ENGINE_LOG_PATH=/app/.dbt/logs \
    DBT_ENGINE_TARGET_PATH=/app/.dbt/target

RUN pip install --no-cache-dir dbt-duckdb==1.11.0 \
    && mkdir -p /app/.dbt/logs /app/.dbt/target /app/data

COPY . .

CMD ["bash"]
