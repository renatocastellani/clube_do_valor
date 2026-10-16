with source as (
    select *
    from "clube_valor"."01_RAW"."clients"
)

select
    client_id as client_id,
    name as name,
    city as city,
    state as state,
    date(created_at) as created_at
from source
where client_id is not null
  and name is not null
  and created_at is not null