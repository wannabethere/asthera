cube(`silver_assets`, {
  sql: `SELECT * FROM silver_assets`,
  
  title: "Silver Assets",
  description: "Silver layer cube for silver_assets",
  
  dimensions: {
    asset_id: {
      sql: `${silver_assets}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    hostname: {
      sql: `${silver_assets}.hostname`,
      type: `string`,
      title: `Hostname`,
    },
    business_unit: {
      sql: `${silver_assets}.business_unit`,
      type: `string`,
      title: `Business Unit`,
    },
    env: {
      sql: `${silver_assets}.env`,
      type: `string`,
      title: `Env`,
    },
    created_at: {
      sql: `${silver_assets}.created_at`,
      type: `time`,
      title: `Created At`,
    },
    updated_at: {
      sql: `${silver_assets}.updated_at`,
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
    criticality: {
      sql: `${silver_assets}.criticality`,
      type: `sum`,
      title: `Criticality`,
    },
  },
  
  
  
  
});
