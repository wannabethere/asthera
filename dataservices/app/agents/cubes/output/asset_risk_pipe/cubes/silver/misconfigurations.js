cube(`silver_misconfigurations`, {
  sql: `SELECT * FROM silver_misconfigurations`,
  
  title: "Silver Misconfigurations",
  description: "Silver layer cube for silver_misconfigurations",
  
  dimensions: {
    asset_id: {
      sql: `${silver_misconfigurations}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    config_id: {
      sql: `${silver_misconfigurations}.config_id`,
      type: `number`,
      title: `Config Id`,
      primaryKey: true,
    },
    severity: {
      sql: `${silver_misconfigurations}.severity`,
      type: `string`,
      title: `Severity`,
    },
    category: {
      sql: `${silver_misconfigurations}.category`,
      type: `string`,
      title: `Category`,
    },
    discovered_at: {
      sql: `${silver_misconfigurations}.discovered_at`,
      type: `time`,
      title: `Discovered At`,
    },
    updated_at: {
      sql: `${silver_misconfigurations}.updated_at`,
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
