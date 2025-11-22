cube(`gold_misconfigurations`, {
  sql: `SELECT * FROM gold_misconfigurations`,
  
  title: "Gold Misconfigurations",
  description: "Gold layer cube for gold_misconfigurations",
  
  dimensions: {
    asset_id: {
      sql: `${gold_misconfigurations}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    config_id: {
      sql: `${gold_misconfigurations}.config_id`,
      type: `number`,
      title: `Config Id`,
      primaryKey: true,
    },
    severity: {
      sql: `${gold_misconfigurations}.severity`,
      type: `string`,
      title: `Severity`,
    },
    category: {
      sql: `${gold_misconfigurations}.category`,
      type: `string`,
      title: `Category`,
    },
    discovered_at: {
      sql: `${gold_misconfigurations}.discovered_at`,
      type: `time`,
      title: `Discovered At`,
    },
    updated_at: {
      sql: `${gold_misconfigurations}.updated_at`,
      type: `time`,
      title: `Updated At`,
    },
  },
  
  measures: {
    count: {
      sql: `1`,
      type: `count`,
      title: `Count`,
      drillMembers: [asset_id, config_id],
    },
  },
  
  
  
  
});
