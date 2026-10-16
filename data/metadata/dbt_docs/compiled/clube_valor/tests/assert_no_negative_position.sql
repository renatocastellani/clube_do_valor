select
    client_id,
    asset_ticker,
    net_quantity,
    net_value
from "clube_valor"."04_MART"."mart_client_portfolio"
where net_quantity < 0