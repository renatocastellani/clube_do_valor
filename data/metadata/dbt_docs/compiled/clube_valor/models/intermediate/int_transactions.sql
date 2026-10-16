with clients_for_join as (
    select
        client_id,
        name,
        city,
        state,
        created_at,
        row_number() over (
            partition by client_id
            order by
                case when city is null then 1 else 0 end,
                created_at,
                name,
                state
        ) as client_rank
    from "clube_valor"."02_STG"."stg_clients"
)

select
    t.transaction_id,
    t.client_id,
    c.name as client_name,
    c.city,
    c.state,
    c.created_at as client_created_at,
    t.asset_ticker,
    t.operation,
    t.quantity,
    t.unit_price,
    t.quantity * t.unit_price as transaction_value,
    t.transaction_date
from "clube_valor"."02_STG"."stg_transactions" as t
left join clients_for_join as c
    on t.client_id = c.client_id
    and c.client_rank = 1