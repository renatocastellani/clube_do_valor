
    
    

select
    transaction_id as unique_field,
    count(*) as n_records

from "clube_valor"."01_RAW"."transactions"
where transaction_id is not null
group by transaction_id
having count(*) > 1


