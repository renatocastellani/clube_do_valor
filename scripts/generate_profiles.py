"""Gera relatórios YData para os objetos analíticos do DuckDB."""

from pathlib import Path

import duckdb
from ydata_profiling import ProfileReport


DATABASE_PATH = Path("/app/data/clube_valor.duckdb")
OUTPUT_DIR = Path("/app/data/metadata/results_profiling")


def quote_identifier(value):
    return f'"{value.replace("\"", "\"\"")}"'


def main():
    if not DATABASE_PATH.exists():
        raise SystemExit("Banco DuckDB não encontrado. Execute dbt seed e dbt run antes do profiling.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(DATABASE_PATH), read_only=True)
    objects = connection.execute(
        """select table_schema, table_name, table_type
        from information_schema.tables
        where table_schema in ('01_RAW', '02_STG', '03_INT', '04_MART')
        order by table_schema, table_name"""
    ).fetchall()

    for schema, name, object_type in objects:
        dataframe = connection.execute(
            f"select * from {quote_identifier(schema)}.{quote_identifier(name)}"
        ).fetchdf()
        report_name = f"{schema}.{name}"
        destination = OUTPUT_DIR / f"{report_name}.html"
        ProfileReport(
            dataframe,
            title=f"Profiling — {report_name} ({object_type.lower()})",
            explorative=True,
        ).to_file(destination)
        print(f"Gerado: {destination}")

    connection.close()


if __name__ == "__main__":
    main()
