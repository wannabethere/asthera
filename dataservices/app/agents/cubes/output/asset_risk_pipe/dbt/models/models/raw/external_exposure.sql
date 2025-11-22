-- dbt model: external_exposure
{{ config(materialized='table') }}

SELECT * FROM public.external_exposure