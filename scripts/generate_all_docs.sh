#!/usr/bin/env bash

# Permite executar o script a partir de qualquer diretório.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Não usamos `set -e`: dbt test e dbt build podem retornar código diferente
# de zero por falhas de qualidade, mas seus relatórios ainda precisam ser gerados.
set -u

status=0

run_required() {
  echo
  echo "==> $*"
  "$@"
  step_status=$?
  if [ "$step_status" -ne 0 ]; then
    echo "Comando encerrado com código $step_status; não é seguro gerar artefatos com dados incompletos."
    exit "$step_status"
  fi
}

run_report_step() {
  echo
  echo "==> $*"
  "$@"
  step_status=$?
  if [ "$step_status" -ne 0 ]; then
    echo "Comando encerrado com código $step_status; continuando para gerar os artefatos restantes."
    status=1
  fi
}

# Fluxo diagnóstico solicitado no case. `dbt run` materializa as relações que
# serão exploradas no profiling; seed e run precisam terminar com sucesso.
run_required dbt seed
run_required dbt run

# O profiling é feito sobre as relações materializadas por `dbt run` e precisa
# existir antes do relatório de testes, que cria links para esses arquivos.
run_report_step python scripts/generate_profiles.py

# Este relatório deve consumir exatamente o run_results.json do `dbt test`.
# O código diferente de zero é esperado enquanto houver falhas de qualidade.
run_report_step dbt test
run_report_step python scripts/generate_test_results_report.py

# O build é executado separadamente para produzir seu próprio run_results.json,
# com seeds, modelos, testes e recursos bloqueados pela ordem de dependências.
run_report_step dbt build
run_report_step python scripts/generate_build_results_report.py

exit "$status"
