#!/usr/bin/env python3
"""Gera um relatório HTML da última execução de dbt build."""

from collections import defaultdict
from html import escape
import json
from pathlib import Path

from generate_test_results_report import (
    PROFILING_DIR,
    badge,
    display_name,
    format_datetime,
    format_duration,
    page,
    read_failure_rows,
    read_manifest_nodes,
    status_kind,
)


INPUT_PATH = Path(".dbt/target/run_results.json")
OUTPUT_PATH = Path("data/metadata/results_build/last_build_results.html")


def build_target(result, nodes):
    """Retorna o objeto lógico ao qual um resultado do build pertence."""
    node = nodes.get(result.get("unique_id"), {})
    target_id = result.get("unique_id")
    if node.get("resource_type") == "test":
        target_id = node.get("attached_node")
        if not target_id:
            target_id = next(
                (item for item in node.get("depends_on", {}).get("nodes", []) if item in nodes),
                result.get("unique_id"),
            )
        node = nodes.get(target_id, {})

    name = node.get("name", display_name(result))
    resource_type = node.get("resource_type", "resource")
    materialization = node.get("config", {}).get("materialized")
    kind = materialization or resource_type
    schema = node.get("config", {}).get("schema") or node.get("schema")
    full_name = f"{schema}.{name}" if schema else name
    profile_name = f"{full_name}.html"
    return {
        "id": target_id or "unidentified",
        "label": f"{full_name} · {kind}",
        "details": f"Schema: {schema}" if schema else "Origem não identificada no manifest.json",
        "sort_key": (schema or "ZZZ", name),
        "profile_href": f"../results_profiling/{profile_name}",
        "profile_ready": (PROFILING_DIR / profile_name).exists(),
    }


def build_card(result, target, detail, audit_error, nodes):
    kind = status_kind(result.get("status", "skipped"))
    node = nodes.get(result.get("unique_id"), {})
    resource_type = node.get("resource_type", "resource")
    name = display_name(result)
    if resource_type != "test":
        name = f"{resource_type}: {name}"
    failures = "—" if result.get("failures") is None else str(result["failures"])
    message = result.get("message") or (
        "Recurso não executado porque uma dependência falhou."
        if kind == "skipped"
        else "Sem detalhes adicionais retornados pelo dbt."
    )

    failure_details = ""
    if detail:
        header = "".join(f"<th>{escape(column)}</th>" for column in detail["columns"])
        rows = "".join(
            "<tr>"
            + "".join(f"<td>{escape('' if value is None else str(value))}</td>" for value in row)
            + "</tr>"
            for row in detail["rows"]
        )
        failure_details = (
            f'<details class="failure-details"><summary>Ver registros afetados '
            f'({len(detail["rows"])})</summary><div class="table-scroll"><table>'
            f"<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div></details>"
        )
    elif result.get("failures"):
        failure_details = (
            f'<p class="details-note">Registros detalhados indisponíveis. '
            f'{escape(audit_error or "Execute dbt build para recriar a auditoria.")}</p>'
        )

    return f"""
      <article class="result-card {kind}" data-status="{kind}" data-origin="{escape(target['id'], quote=True)}">
        <div class="result-heading"><div><h3>{escape(name)}</h3><p class="identifier">{escape(result.get('unique_id', ''))}</p></div>{badge(result.get('status', 'desconhecido'))}</div>
        <dl><div><dt>Registros retornados</dt><dd>{escape(failures)}</dd></div><div><dt>Tempo de execução</dt><dd>{format_duration(result.get('execution_time'))}</dd></div></dl>
        <p class="message">{escape(message)}</p>
        {failure_details}
      </article>"""


def empty_build_report(reason, tone="warning"):
    body = (
        '<header><h1>Resultados do dbt build</h1>'
        '<p class="subtitle">Visão da última execução disponível</p></header>'
        f'<section class="notice {tone}"><h2>Nenhum resultado de build disponível</h2>'
        f"<p>{escape(reason)}</p></section>"
        '<section><h2>Como gerar o relatório</h2>'
        '<p>Execute <code>dbt build</code> e, em seguida, '
        '<code>python scripts/generate_build_results_report.py</code>.</p></section>'
    )
    return page("Resultados do dbt build", body)


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not INPUT_PATH.exists():
        OUTPUT_PATH.write_text(
            empty_build_report("O arquivo run_results.json ainda não existe."), encoding="utf-8"
        )
        return
    try:
        payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        OUTPUT_PATH.write_text(empty_build_report(f"Não foi possível ler run_results.json: {error}", "error"), encoding="utf-8")
        return

    command = payload.get("args", {}).get("which", "desconhecido")
    if command != "build":
        OUTPUT_PATH.write_text(
            empty_build_report(
                f"O último artefato foi gerado por `dbt {command}`, não por `dbt build`."
            ),
            encoding="utf-8",
        )
        return

    nodes = read_manifest_nodes()
    results = payload.get("results", [])
    enriched = [(item, build_target(item, nodes)) for item in results]
    failure_rows, audit_error = read_failure_rows(results, nodes)
    groups = defaultdict(list)
    for item, target in enriched:
        groups[target["id"]].append((item, target))

    status_order = {"failed": 0, "warning": 1, "skipped": 2, "passed": 3}
    group_html = []
    for items in sorted(groups.values(), key=lambda group: group[0][1]["sort_key"]):
        target = items[0][1]
        ordered = sorted(
            items,
            key=lambda pair: (
                status_order[status_kind(pair[0].get("status", "skipped"))],
                pair[0].get("unique_id", ""),
            ),
        )
        cards = "".join(
            build_card(item, target, failure_rows.get(item.get("unique_id")), audit_error, nodes)
            for item, _ in ordered
        )
        if target["profile_ready"]:
            profile_button = (
                f'<a class="profile-link" href="{escape(target["profile_href"], quote=True)}" '
                f'target="_blank" rel="noopener" title="Abrir profiling de '
                f'{escape(target["label"], quote=True)}" aria-label="Abrir profiling">↗</a>'
            )
        else:
            profile_button = (
                f'<span class="profile-link unavailable" title="Profiling ainda não gerado para '
                f'{escape(target["label"], quote=True)}" aria-label="Profiling ainda não gerado">↗</span>'
            )
        group_html.append(
            f'<section class="origin-group" data-origin="{escape(target["id"], quote=True)}">'
            f'<div class="origin-heading"><div><h2>{escape(target["label"])}</h2>'
            f'<p>{escape(target["details"])}</p></div>{profile_button}</div>{cards}</section>'
        )

    counts = {
        kind: sum(status_kind(item.get("status", "skipped")) == kind for item in results)
        for kind in ("passed", "failed", "warning", "skipped")
    }
    origins = {target["id"]: target for _, target in enriched}
    options = "".join(
        f'<option value="{escape(origin_id, quote=True)}">{escape(target["label"])}</option>'
        for origin_id, target in sorted(origins.items(), key=lambda pair: pair[1]["sort_key"])
    )
    notice = (
        '<section class="notice error"><h2>Build bloqueado</h2>'
        f'<p>{counts["failed"]} teste(s) falharam e {counts["skipped"]} recurso(s) downstream '
        'foram ignorados. Os modelos ignorados não foram reconstruídos nesta execução.</p></section>'
        if counts["failed"]
        else '<section class="notice"><h2>Build concluído</h2><p>Todos os recursos selecionados foram processados sem falhas críticas.</p></section>'
    )
    body = f"""
      <header><h1>Resultados do dbt build</h1><p class="subtitle">Execução da pipeline com testes e bloqueio de dependências</p><div class="metadata"><div><strong>Última execução</strong>{format_datetime(payload.get('metadata', {}).get('generated_at'))}</div><div><strong>Comando</strong>dbt build</div><div><strong>Duração total</strong>{format_duration(payload.get('elapsed_time'))}</div></div></header>
      {notice}
      <section class="controls"><button class="metric" type="button" data-status-filter="all"><strong>{len(results)}</strong><span>todos os recursos</span></button><button class="metric passed" type="button" data-status-filter="passed"><strong>{counts['passed']}</strong><span>passaram</span></button><button class="metric failed" type="button" data-status-filter="failed"><strong>{counts['failed']}</strong><span>falharam</span></button><button class="metric warning" type="button" data-status-filter="warning"><strong>{counts['warning']}</strong><span>alertas</span></button><button class="metric" type="button" data-status-filter="skipped"><strong>{counts['skipped']}</strong><span>ignorados</span></button><label class="filter-field" for="origin-filter">Tabela ou view<span class="filter-control"><select id="origin-filter"><option value="">Todos os objetos</option>{options}</select><button id="clear-filters" class="clear" type="button">Limpar</button></span></label></section>
      <p id="filter-summary" class="filter-summary" aria-live="polite"></p>
      <section><h2>Resultados por tabela, view ou seed</h2><p class="section-note">Falhas aparecem primeiro; recursos ignorados indicam bloqueio por uma dependência upstream.</p>{''.join(group_html)}</section>"""
    OUTPUT_PATH.write_text(page("Resultados do dbt build", body), encoding="utf-8")


if __name__ == "__main__":
    main()
