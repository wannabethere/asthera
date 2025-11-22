cube(`silver_software_inventory`, {
  sql: `SELECT * FROM silver_software_inventory`,
  
  title: "Silver Software Inventory",
  description: "Silver layer cube for silver_software_inventory",
  
  dimensions: {
    asset_id: {
      sql: `${silver_software_inventory}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    software_name: {
      sql: `${silver_software_inventory}.software_name`,
      type: `string`,
      title: `Software Name`,
    },
    version: {
      sql: `${silver_software_inventory}.version`,
      type: `string`,
      title: `Version`,
    },
    is_eol: {
      sql: `${silver_software_inventory}.is_eol`,
      type: `string`,
      title: `Is Eol`,
    },
    is_unsupported: {
      sql: `${silver_software_inventory}.is_unsupported`,
      type: `string`,
      title: `Is Unsupported`,
    },
    discovered_at: {
      sql: `${silver_software_inventory}.discovered_at`,
      type: `time`,
      title: `Discovered At`,
    },
    updated_at: {
      sql: `${silver_software_inventory}.updated_at`,
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
  },
  
  
  
  
});
