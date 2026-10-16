

select
    transaction_id,
    client_id,
    asset_ticker,
    operation,
    quantity,
    unit_price,
    transaction_value,
    transaction_date
from "clube_valor"."03_INT"."int_transactions"

where transaction_date > (
    select coalesce(max(transaction_date), cast('1900-01-01' as date))
    from "clube_valor"."04_MART"."fact_transactions"
)
