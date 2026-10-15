{{ config(materialized='table') }}

select
    client_id,
    asset_ticker,
    sum({{ signed_operation_value('quantity') }}) as net_quantity,
    sum({{ signed_operation_value('transaction_value') }}) as net_value
from {{ ref('fact_transactions') }}
group by client_id, asset_ticker
