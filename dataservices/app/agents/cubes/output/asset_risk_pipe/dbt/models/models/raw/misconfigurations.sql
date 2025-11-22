-- dbt model: misconfigurations
{{ config(materialized='table') }}

SELECT * FROM public.misconfigurations