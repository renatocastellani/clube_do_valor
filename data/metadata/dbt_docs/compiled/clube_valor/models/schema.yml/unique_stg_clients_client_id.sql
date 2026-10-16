
    
    

select
    client_id as unique_field,
    count(*) as n_records

from "clube_valor"."02_STG"."stg_clients"
where client_id is not null
group by client_id
having count(*) > 1


