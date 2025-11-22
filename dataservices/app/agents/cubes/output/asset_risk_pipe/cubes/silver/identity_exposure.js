cube(`silver_identity_exposure`, {
  sql: `SELECT * FROM silver_identity_exposure`,
  
  title: "Silver Identity Exposure",
  description: "Silver layer cube for silver_identity_exposure",
  
  dimensions: {
    asset_id: {
      sql: `${silver_identity_exposure}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    has_password_reuse: {
      sql: `${silver_identity_exposure}.has_password_reuse`,
      type: `string`,
      title: `Has Password Reuse`,
    },
    has_mfa_disabled: {
      sql: `${silver_identity_exposure}.has_mfa_disabled`,
      type: `string`,
      title: `Has Mfa Disabled`,
    },
    assessed_at: {
      sql: `${silver_identity_exposure}.assessed_at`,
      type: `time`,
      title: `Assessed At`,
    },
    updated_at: {
      sql: `${silver_identity_exposure}.updated_at`,
      type: `time`,
      title: `Updated At`,
    },
  },
  
  measures: {
    count: {
      sql: `1`,
      type: `count`,
      title: `Count`,
      drillMembers: [asset_id],
    },
    num_admin_accounts: {
      sql: `${silver_identity_exposure}.num_admin_accounts`,
      type: `sum`,
      title: `Num Admin Accounts`,
    },
    num_stale_accounts: {
      sql: `${silver_identity_exposure}.num_stale_accounts`,
      type: `sum`,
      title: `Num Stale Accounts`,
    },
  },
  
  
  
  
});
