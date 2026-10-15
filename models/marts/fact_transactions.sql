{{ config(
    materialized='incremental',
    unique_key='transaction_id',
    incremental_strategy='merge',
    on_schema_change='fail'
) }}

select
    transaction_id,
    client_id,
    asset_ticker,
    operation,
    quantity,
    unit_price,
    transaction_value,
    transaction_date
from {{ ref('int_transactions') }}
{% if is_incremental() %}
where transaction_date > (
    select coalesce(max(transaction_date), cast('1900-01-01' as date))
    from {{ this }}
)
{% endif %}
