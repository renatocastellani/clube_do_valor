select
    transaction_id,
    quantity,
    unit_price
from {{ ref('transactions') }}
where quantity <= 0
   or unit_price <= 0
