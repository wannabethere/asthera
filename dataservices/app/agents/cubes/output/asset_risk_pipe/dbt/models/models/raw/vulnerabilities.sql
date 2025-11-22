-- dbt model: vulnerabilities
{{ config(materialized='table') }}

SELECT * FROM public.vulnerabilities