{{ config(materialized='table') }}

select
    client_id,
    name,
    city,
    state,
    created_at
from {{ ref('stg_clients') }}
