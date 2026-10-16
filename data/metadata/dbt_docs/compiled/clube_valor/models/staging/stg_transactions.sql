with source as (
    select *
    from "clube_valor"."01_RAW"."transactions"
)

select
    transaction_id as transaction_id,
    client_id as client_id,
    asset_ticker as asset_ticker,
    upper(operation) as operation,
    cast(quantity as integer) as quantity,
    cast(unit_price as real) as unit_price,
    date(transaction_date) as transaction_date
from source
where transaction_id is not null
  and client_id is not null
  and asset_ticker is not null
  and operation in ('BUY', 'SELL')
  and quantity > 0
  and unit_price > 0
  and transaction_date is not null