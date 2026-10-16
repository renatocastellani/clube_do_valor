select
    transaction_id,
    quantity,
    unit_price
from "clube_valor"."01_RAW"."transactions"
where quantity <= 0
   or unit_price <= 0