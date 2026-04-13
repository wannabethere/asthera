-- PostgreSQL comments for ds_dp_* (data services RLS/CLS store)

COMMENT ON TABLE ds_dp_org_settings IS 'Per-organization data protection header (version + summary).';
COMMENT ON COLUMN ds_dp_org_settings.organization_id IS 'Tenant UUID; maps to gateway DEFAULT_ORG_ID or external org id.';
COMMENT ON TABLE ds_dp_roles IS 'Application roles used in CLS/session documentation (no hardcoded policies).';
COMMENT ON TABLE ds_dp_session_properties IS 'Session property keys bound at query time for policy evaluation.';
COMMENT ON TABLE ds_dp_rls_policies IS 'Row-level predicates per model_ref; parameters must bind session properties.';
COMMENT ON TABLE ds_dp_cls_policies IS 'Column-level rules: protected_columns gated by session_property vs allowed_values.';
