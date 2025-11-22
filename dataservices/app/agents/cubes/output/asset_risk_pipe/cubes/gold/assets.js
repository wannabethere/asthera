cube(`gold_assets`, {
  sql: `SELECT * FROM gold_assets`,
  
  title: "Gold Assets",
  description: "Gold layer cube for gold_assets",
  
  dimensions: {
    asset_id: {
      sql: `${gold_assets}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    hostname: {
      sql: `${gold_assets}.hostname`,
      type: `string`,
      title: `Hostname`,
    },
    business_unit: {
      sql: `${gold_assets}.business_unit`,
      type: `string`,
      title: `Business Unit`,
    },
    env: {
      sql: `${gold_assets}.env`,
      type: `string`,
      title: `Env`,
    },
    created_at: {
      sql: `${gold_assets}.created_at`,
      type: `time`,
      title: `Created At`,
    },
    updated_at: {
      sql: `${gold_assets}.updated_at`,
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
      sql: `${gold_assets}.criticality`,
      type: `sum`,
      title: `Criticality`,
    },
  },
  
  
  
  
});
