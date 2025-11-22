-- dbt model: enrollments
{{ config(materialized='table') }}

SELECT * FROM public.enrollments