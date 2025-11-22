cube(`silver_vulnerabilities`, {
  sql: `SELECT * FROM silver_vulnerabilities`,
  
  title: "Silver Vulnerabilities",
  description: "Silver layer cube for silver_vulnerabilities",
  
  dimensions: {
    asset_id: {
      sql: `${silver_vulnerabilities}.asset_id`,
      type: `number`,
      title: `Asset Id`,
      primaryKey: true,
    },
    cve_id: {
      sql: `${silver_vulnerabilities}.cve_id`,
      type: `string`,
      title: `Cve Id`,
    },
    is_kev: {
      sql: `${silver_vulnerabilities}.is_kev`,
      type: `string`,
      title: `Is Kev`,
    },
    is_internet_facing: {
      sql: `${silver_vulnerabilities}.is_internet_facing`,
      type: `string`,
      title: `Is Internet Facing`,
    },
    discovered_at: {
      sql: `${silver_vulnerabilities}.discovered_at`,
      type: `time`,
      title: `Discovered At`,
    },
    updated_at: {
      sql: `${silver_vulnerabilities}.updated_at`,
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
      sql: `${silver_vulnerabilities}.cvss_score`,
      type: `sum`,
      title: `Cvss Score`,
    },
    epss_score: {
      sql: `${silver_vulnerabilities}.epss_score`,
      type: `sum`,
      title: `Epss Score`,
    },
  },
  
  
  
  
});
