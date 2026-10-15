{% macro signed_operation_value(column_name) %}
    case
        when operation = 'BUY' then {{ column_name }}
        else -{{ column_name }}
    end
{% endmacro %}
