-- dbt model: assets
{{ config(materialized='table') }}

SELECT * FROM public.assets