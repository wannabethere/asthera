-- dbt model: identity_exposure
{{ config(materialized='table') }}

SELECT * FROM public.identity_exposure