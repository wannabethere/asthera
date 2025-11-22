-- dbt model: software_inventory
{{ config(materialized='table') }}

SELECT * FROM public.software_inventory