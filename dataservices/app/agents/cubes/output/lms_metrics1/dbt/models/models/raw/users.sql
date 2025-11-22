-- dbt model: users
{{ config(materialized='table') }}

SELECT * FROM public.users