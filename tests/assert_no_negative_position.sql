select
    client_id,
    asset_ticker,
    net_quantity,
    net_value
from {{ ref('mart_client_portfolio') }}
where net_quantity < 0
