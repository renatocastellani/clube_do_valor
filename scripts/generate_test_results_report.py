#!/usr/bin/env python3
"""Gera um relatório HTML autocontido a partir do último run_results.json do dbt."""

from collections import defaultdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo


INPUT_PATH = Path(".dbt/target/run_results.json")
MANIFEST_PATH = Path(".dbt/target/manifest.json")
DATABASE_PATH = Path("data/clube_valor.duckdb")
OUTPUT_PATH = Path("data/metadata/results_tests/last_test_results.html")
PROFILING_DIR = Path("data/metadata/results_profiling")
SUCCESS_STATUSES = {"pass", "success"}
MAX_FAILURE_ROWS = 100


def format_datetime(value):
    if not value:
        return "Data não informada"
    try:
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M:%S (BRT)")
    except ValueError:
        return value


def format_duration(seconds):
    return f"{float(seconds or 0):.2f} s".replace(".", ",")


def status_kind(status):
    status = status.lower()
    if status in SUCCESS_STATUSES:
        return "passed"
    if status in {"fail", "error"}:
        return "failed"
    if status == "warn":
        return "warning"
    return "skipped"


def display_name(result):
    parts = result.get("unique_id", "Teste sem identificador").split(".", 2)
    return parts[-1] if len(parts) == 3 else parts[0]


def read_manifest_nodes():
    if not MANIFEST_PATH.exists():
        return {}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return {**manifest.get("nodes", {}), **manifest.get("sources", {})}
    except (OSError, json.JSONDecodeError):
        return {}


def test_target(result, nodes):
    test = nodes.get(result.get("unique_id"), {})
    target_id = test.get("attached_node")
    if not target_id:
        target_id = next((item for item in test.get("depends_on", {}).get("nodes", []) if item in nodes), None)
    target = nodes.get(target_id, {})
    name = target.get("name", "Objeto não identificado")
    materialization = target.get("config", {}).get("materialized")
    kind = materialization or ("seed" if target.get("resource_type") == "seed" else target.get("resource_type", "objeto"))
    schema = target.get("config", {}).get("schema") or target.get("schema")
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


def quote_identifier(value):
    return f'"{value.replace("\"", "\"\"")}"'


def read_failure_rows(results, nodes):
    """Lê os registros materializados pelo store_failures, quando disponíveis."""
    if not DATABASE_PATH.exists():
        return {}, "Banco DuckDB não encontrado."
    try:
        import duckdb

        connection = duckdb.connect(str(DATABASE_PATH), read_only=True)
        audit_tables = {
            table_name: schema
            for schema, table_name in connection.execute(
                """select table_schema, table_name
                from information_schema.tables
                where table_schema like '%dbt_test__audit'"""
            ).fetchall()
        }
        details = {}
        for result in results:
            if not result.get("failures"):
                continue
            test_name = nodes.get(result.get("unique_id"), {}).get("name")
            schema = audit_tables.get(test_name)
            if not schema:
                continue
            cursor = connection.execute(
                f"select * from {quote_identifier(schema)}.{quote_identifier(test_name)} limit {MAX_FAILURE_ROWS}"
            )
            details[result["unique_id"]] = {
                "columns": [column[0] for column in cursor.description],
                "rows": cursor.fetchall(),
            }
        connection.close()
        return details, None
    except Exception as error:
        return {}, f"Não foi possível ler as tabelas de auditoria: {error}"


def badge(status):
    labels = {"pass": "Passou", "success": "Sucesso", "fail": "Falhou", "error": "Erro", "warn": "Alerta", "skipped": "Ignorado"}
    return f'<span class="badge {status_kind(status)}">{escape(labels.get(status.lower(), status.title()))}</span>'


def result_card(result, target, detail, audit_error):
    kind = status_kind(result.get("status", "skipped"))
    failures = "—" if result.get("failures") is None else str(result["failures"])
    message = result.get("message") or "Sem detalhes adicionais retornados pelo dbt."
    if detail:
        header = "".join(f"<th>{escape(column)}</th>" for column in detail["columns"])
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape('' if value is None else str(value))}</td>" for value in row) + "</tr>"
            for row in detail["rows"]
        )
        failure_details = f'<details class="failure-details"><summary>Ver registros afetados ({len(detail["rows"])})</summary><div class="table-scroll"><table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div></details>'
    elif result.get("failures"):
        failure_details = f'<p class="details-note">Registros detalhados indisponíveis. {escape(audit_error or "Execute dbt test para recriar a auditoria.")}</p>'
    else:
        failure_details = ""
    return f"""
      <article class="result-card {kind}" data-status="{kind}" data-origin="{escape(target['id'], quote=True)}">
        <div class="result-heading"><div><h3>{escape(display_name(result))}</h3><p class="identifier">{escape(result.get('unique_id', ''))}</p></div>{badge(result.get('status', 'desconhecido'))}</div>
        <dl><div><dt>Registros retornados</dt><dd>{escape(failures)}</dd></div><div><dt>Tempo de execução</dt><dd>{format_duration(result.get('execution_time'))}</dd></div></dl>
        <p class="message">{escape(message)}</p>
        {failure_details}
      </article>"""


def page(title, body):
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title>
<style>
:root {{--ink:#16243a;--muted:#60708a;--line:#dce3ec;--surface:#fff;--canvas:#f4f7fb;--green:#087f5b;--green-bg:#e6f6ef;--red:#c92a2a;--red-bg:#fff0f0;--amber:#a05a00;--amber-bg:#fff7e6;--blue:#1769aa}} *{{box-sizing:border-box}} body{{margin:0;color:var(--ink);background:var(--canvas);font-family:Inter,ui-sans-serif,system-ui,sans-serif;line-height:1.5}} main{{width:min(1120px,calc(100% - 32px));margin:40px auto 64px}} header{{padding:30px 32px;border-radius:16px;color:#fff;background:linear-gradient(120deg,#0b466d,#1769aa);box-shadow:0 12px 30px #0b466d2b}} h1{{margin:0 0 8px;font-size:clamp(1.65rem,4vw,2.4rem)}} h2{{margin:36px 0 14px;font-size:1.25rem}} h3{{margin:0;font-size:1rem;overflow-wrap:anywhere}} .subtitle{{margin:0;color:#d7edff}} .metadata{{display:flex;flex-wrap:wrap;gap:12px 28px;margin-top:24px;font-size:.94rem}} .metadata strong{{display:block;color:#d7edff;font-size:.75rem;letter-spacing:.04em;text-transform:uppercase}}
.notice{{margin-top:26px;padding:20px 22px;border:1px solid;border-radius:12px;background:var(--surface)}}.notice.warning{{border-color:#f0c36a;background:var(--amber-bg)}}.notice.error{{border-color:#f1aaaa;background:var(--red-bg)}}.notice h2{{margin:0 0 6px;font-size:1.1rem}}.notice p{{margin:0}}.controls{{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:14px;margin-top:26px}}.metric{{width:100%;padding:18px;border:1px solid var(--line);border-radius:12px;color:var(--ink);background:var(--surface);text-align:left;cursor:pointer}}.metric:hover,.metric[aria-pressed="true"]{{outline:3px solid #1769aa33;border-color:var(--blue)}}.metric strong{{display:block;font-size:1.9rem;line-height:1.1}}.metric span,.section-note{{color:var(--muted);font-size:.87rem}}.metric.passed strong{{color:var(--green)}}.metric.failed strong{{color:var(--red)}}.metric.warning strong{{color:var(--amber)}}
.filter-field{{grid-column:span 3;display:grid;gap:5px;min-height:98px;padding:13px 16px;border:1px solid var(--line);border-radius:12px;background:var(--surface);color:var(--muted);font-size:.82rem;font-weight:700}}.filter-control{{display:flex;gap:8px;align-items:center}}select,button{{font:inherit}}select{{min-width:0;flex:1;padding:4px 0;border:0;color:var(--ink);background:#fff;font-weight:700}}.clear{{padding:3px 0;border:0;color:var(--blue);background:#fff;cursor:pointer;white-space:nowrap}}.clear:disabled{{color:var(--muted);cursor:not-allowed}}.filter-summary{{margin:10px 0 0;color:var(--muted);font-size:.9rem}}
.origin-group{{margin:18px 0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--surface)}}.origin-heading{{display:flex;align-items:start;justify-content:space-between;gap:16px;padding:17px 20px;border-bottom:1px solid var(--line);background:#fbfcfe}}.origin-heading h2{{margin:0;font-size:1.08rem}}.origin-heading p{{margin:3px 0 0;color:var(--muted);font-size:.86rem}}.profile-link{{display:grid;place-items:center;flex:none;width:32px;height:32px;border:1px solid var(--blue);border-radius:8px;color:var(--blue);background:#fff;font-size:1.2rem;font-weight:700;text-decoration:none}}.profile-link:hover{{background:#edf6ff}}.profile-link.unavailable{{border-color:var(--line);color:var(--muted);cursor:not-allowed}}.result-card{{padding:18px 20px;border-left:5px solid var(--blue);border-bottom:1px solid var(--line)}}.result-card:last-child{{border-bottom:0}}.result-card.passed{{border-left-color:var(--green)}}.result-card.failed{{border-left-color:var(--red)}}.result-card.warning{{border-left-color:var(--amber)}}.result-heading{{display:flex;align-items:start;justify-content:space-between;gap:18px}}.identifier{{margin:3px 0 0;color:var(--muted);font-family:ui-monospace,monospace;font-size:.77rem;overflow-wrap:anywhere}}.badge{{display:inline-block;flex:none;padding:4px 9px;border-radius:99px;font-size:.76rem;font-weight:700}}.badge.passed{{color:var(--green);background:var(--green-bg)}}.badge.failed{{color:var(--red);background:var(--red-bg)}}.badge.warning{{color:var(--amber);background:var(--amber-bg)}}.badge.skipped{{color:var(--muted);background:#eef1f5}}dl{{display:flex;flex-wrap:wrap;gap:8px 38px;margin:16px 0 10px}}dl div{{display:flex;gap:7px}}dt{{color:var(--muted)}}dd{{margin:0;font-weight:700}}.message{{margin:0;padding-top:11px;border-top:1px solid var(--line);color:#34445a;white-space:pre-wrap}}.failure-details{{margin-top:12px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fbfcfe}}.failure-details summary{{color:var(--blue);font-weight:700;cursor:pointer}}.table-scroll{{overflow:auto;margin-top:12px}}table{{width:100%;border-collapse:collapse;font-size:.88rem}}th,td{{padding:8px 10px;border:1px solid var(--line);text-align:left;white-space:nowrap}}th{{background:#eef4fa}}.details-note{{margin:12px 0 0;color:var(--muted);font-size:.88rem}}[hidden]{{display:none!important}}footer{{margin-top:36px;color:var(--muted);font-size:.82rem}}@media(max-width:720px){{main{{width:min(100% - 24px,1120px);margin-top:12px}}header{{padding:24px}}.controls{{grid-template-columns:repeat(2,1fr)}}.filter-field{{grid-column:span 2}}.result-heading{{display:block}}.badge{{margin-top:10px}}.profile-link{{margin-top:6px}}}}
</style></head><body><main>{body}<footer>Relatório gerado localmente a partir de <code>.dbt/target/run_results.json</code> e <code>manifest.json</code>.</footer></main>
<script>
const origin=document.querySelector('#origin-filter');if(origin){{const buttons=document.querySelectorAll('[data-status-filter]'),clear=document.querySelector('#clear-filters'),summary=document.querySelector('#filter-summary');let status='all';function apply(){{let visible=0;document.querySelectorAll('.result-card').forEach(card=>{{const match=(status==='all'||card.dataset.status===status)&&(!origin.value||card.dataset.origin===origin.value);card.hidden=!match;if(match)visible+=1}});document.querySelectorAll('.origin-group').forEach(group=>group.hidden=!group.querySelector('.result-card:not([hidden])'));buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.statusFilter===status)));clear.disabled=status==='all'&&!origin.value;summary.textContent=`${{visible}} teste(s) exibido(s).`}}buttons.forEach(button=>button.addEventListener('click',()=>{{status=button.dataset.statusFilter;apply()}}));origin.addEventListener('change',apply);clear.addEventListener('click',()=>{{status='all';origin.value='';apply()}});apply();}}
</script></body></html>"""


def empty_report(reason, tone="warning"):
    body = f'<header><h1>Resultados dos testes dbt</h1><p class="subtitle">Visão da última execução disponível</p></header><section class="notice {tone}"><h2>Nenhum resultado de teste disponível</h2><p>{escape(reason)}</p></section><section><h2>Como gerar o relatório</h2><p>Execute <code>dbt test</code> e, em seguida, <code>python scripts/generate_test_results_report.py</code>.</p></section>'
    return page("Resultados dos testes dbt", body)


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not INPUT_PATH.exists():
        OUTPUT_PATH.write_text(empty_report("O arquivo run_results.json ainda não existe. Nenhum comando dbt foi registrado neste ambiente."), encoding="utf-8")
        return
    try:
        payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        OUTPUT_PATH.write_text(empty_report(f"Não foi possível ler run_results.json: {error}", "error"), encoding="utf-8")
        return

    command = payload.get("args", {}).get("which", "desconhecido")
    nodes = read_manifest_nodes()
    results = [item for item in payload.get("results", []) if item.get("unique_id", "").startswith("test.")]
    if command != "test" and not results:
        OUTPUT_PATH.write_text(empty_report(f"O último artefato foi gerado por `dbt {command}`, não por `dbt test`. Execute os testes novamente para atualizar este relatório."), encoding="utf-8")
        return

    enriched = [(item, test_target(item, nodes)) for item in results]
    failure_rows, audit_error = read_failure_rows(results, nodes)
    groups = defaultdict(list)
    for item, target in enriched:
        groups[target["id"]].append((item, target))
    order = {"failed": 0, "warning": 1, "passed": 2, "skipped": 3}
    group_html = []
    for items in sorted(groups.values(), key=lambda items: items[0][1]["sort_key"]):
        target = items[0][1]
        cards = "".join(result_card(item, target, failure_rows.get(item["unique_id"]), audit_error) for item, _ in sorted(items, key=lambda item: (order[status_kind(item[0].get("status", "skipped"))], display_name(item[0]))))
        if target["profile_ready"]:
            profile_button = f'<a class="profile-link" href="{escape(target["profile_href"], quote=True)}" target="_blank" rel="noopener" title="Abrir profiling de {escape(target["label"], quote=True)}" aria-label="Abrir profiling de {escape(target["label"], quote=True)}">↗</a>'
        else:
            profile_button = f'<span class="profile-link unavailable" title="Profiling ainda não gerado para {escape(target["label"], quote=True)}" aria-label="Profiling ainda não gerado">↗</span>'
        group_html.append(f'<section class="origin-group" data-origin="{escape(target["id"], quote=True)}"><div class="origin-heading"><div><h2>{escape(target["label"])}</h2><p>{escape(target["details"])}</p></div>{profile_button}</div>{cards}</section>')
    counts = {kind: sum(status_kind(item.get("status", "skipped")) == kind for item in results) for kind in ("passed", "failed", "warning", "skipped")}
    origins = {target["id"]: target for _, target in enriched}
    options = "".join(
        f'<option value="{escape(origin_id, quote=True)}">{escape(target["label"])}</option>'
        for origin_id, target in sorted(origins.items(), key=lambda item: item[1]["sort_key"])
    )
    body = f"""
      <header><h1>Resultados dos testes dbt</h1><p class="subtitle">Qualidade dos dados na última execução de testes</p><div class="metadata"><div><strong>Última execução</strong>{format_datetime(payload.get("metadata", {}).get("generated_at"))}</div><div><strong>Comando</strong>dbt {escape(command)}</div><div><strong>Duração total</strong>{format_duration(payload.get("elapsed_time"))}</div></div></header>
      <section class="controls"><button class="metric" type="button" data-status-filter="all"><strong>{len(results)}</strong><span>todos os testes</span></button><button class="metric passed" type="button" data-status-filter="passed"><strong>{counts["passed"]}</strong><span>passaram</span></button><button class="metric failed" type="button" data-status-filter="failed"><strong>{counts["failed"]}</strong><span>falharam</span></button><button class="metric warning" type="button" data-status-filter="warning"><strong>{counts["warning"]}</strong><span>alertas</span></button><button class="metric" type="button" data-status-filter="skipped"><strong>{counts["skipped"]}</strong><span>ignorados</span></button><label class="filter-field" for="origin-filter">Tabela ou view validada<span class="filter-control"><select id="origin-filter"><option value="">Todas as tabelas e views</option>{options}</select><button id="clear-filters" class="clear" type="button">Limpar</button></span></label></section>
      <p id="filter-summary" class="filter-summary" aria-live="polite"></p>
      <section><h2>Resultados por tabela ou view</h2><p class="section-note">Dentro de cada objeto, falhas e alertas aparecem antes dos testes aprovados.</p>{''.join(group_html)}</section>"""
    OUTPUT_PATH.write_text(page("Resultados dos testes dbt", body), encoding="utf-8")


if __name__ == "__main__":
    main()
