cube(`gold_vulnerabilities`, {
  sql: `SELECT * FROM gold_vulnerabilities`,
  
  title: "Gold Vulnerabilities",
  description: "Gold layer cube for gold_vulnerabilities",
  
  dimensions: {
    asset_id: {
      sql: `${gold_vulnerabilities}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    cve_id: {
      sql: `${gold_vulnerabilities}.cve_id`,
      type: `string`,
      title: `Cve Id`,
    },
    is_kev: {
      sql: `${gold_vulnerabilities}.is_kev`,
      type: `string`,
      title: `Is Kev`,
    },
    is_internet_facing: {
      sql: `${gold_vulnerabilities}.is_internet_facing`,
      type: `string`,
      title: `Is Internet Facing`,
    },
    discovered_at: {
      sql: `${gold_vulnerabilities}.discovered_at`,
      type: `time`,
      title: `Discovered At`,
    },
    updated_at: {
      sql: `${gold_vulnerabilities}.updated_at`,
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
    cvss_score: {
      sql: `${gold_vulnerabilities}.cvss_score`,
      type: `sum`,
      title: `Cvss Score`,
    },
    epss_score: {
      sql: `${gold_vulnerabilities}.epss_score`,
      type: `sum`,
      title: `Epss Score`,
    },
  },
  
  
  
  
});
