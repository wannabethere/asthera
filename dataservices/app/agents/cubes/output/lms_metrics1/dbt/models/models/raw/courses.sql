-- dbt model: courses
{{ config(materialized='table') }}

SELECT * FROM public.courses