

select
    client_id,
    asset_ticker,
    sum(
    case
        when operation = 'BUY' then quantity
        else -quantity
    end
) as net_quantity,
    sum(
    case
        when operation = 'BUY' then transaction_value
        else -transaction_value
    end
) as net_value
from "clube_valor"."04_MART"."fact_transactions"
group by client_id, asset_ticker