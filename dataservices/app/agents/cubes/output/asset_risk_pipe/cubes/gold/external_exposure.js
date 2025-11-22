cube(`gold_external_exposure`, {
  sql: `SELECT * FROM gold_external_exposure`,
  
  title: "Gold External Exposure",
  description: "Gold layer cube for gold_external_exposure",
  
  dimensions: {
    asset_id: {
      sql: `${gold_external_exposure}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    is_public_ip: {
      sql: `${gold_external_exposure}.is_public_ip`,
      type: `string`,
      title: `Is Public Ip`,
    },
    weak_tls: {
      sql: `${gold_external_exposure}.weak_tls`,
      type: `string`,
      title: `Weak Tls`,
    },
    geo_risky: {
      sql: `${gold_external_exposure}.geo_risky`,
      type: `string`,
      title: `Geo Risky`,
    },
    scanned_at: {
      sql: `${gold_external_exposure}.scanned_at`,
      type: `time`,
      title: `Scanned At`,
    },
    updated_at: {
      sql: `${gold_external_exposure}.updated_at`,
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
      sql: `${gold_external_exposure}.open_ports`,
      type: `sum`,
      title: `Open Ports`,
    },
  },
  
  
  
  
});
