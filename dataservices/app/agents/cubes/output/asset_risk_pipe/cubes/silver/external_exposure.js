cube(`silver_external_exposure`, {
  sql: `SELECT * FROM silver_external_exposure`,
  
  title: "Silver External Exposure",
  description: "Silver layer cube for silver_external_exposure",
  
  dimensions: {
    asset_id: {
      sql: `${silver_external_exposure}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    is_public_ip: {
      sql: `${silver_external_exposure}.is_public_ip`,
      type: `string`,
      title: `Is Public Ip`,
    },
    weak_tls: {
      sql: `${silver_external_exposure}.weak_tls`,
      type: `string`,
      title: `Weak Tls`,
    },
    geo_risky: {
      sql: `${silver_external_exposure}.geo_risky`,
      type: `string`,
      title: `Geo Risky`,
    },
    scanned_at: {
      sql: `${silver_external_exposure}.scanned_at`,
      type: `time`,
      title: `Scanned At`,
    },
    updated_at: {
      sql: `${silver_external_exposure}.updated_at`,
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
    open_ports: {
      sql: `${silver_external_exposure}.open_ports`,
      type: `sum`,
      title: `Open Ports`,
    },
  },
  
  
  
  
});
