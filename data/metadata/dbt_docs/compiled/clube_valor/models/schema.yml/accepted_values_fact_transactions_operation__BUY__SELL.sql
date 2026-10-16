
    
    

with all_values as (

    select
        operation as value_field,
        count(*) as n_records

    from "clube_valor"."04_MART"."fact_transactions"
    group by operation

)

select *
from all_values
where value_field not in (
    'BUY','SELL'
)


