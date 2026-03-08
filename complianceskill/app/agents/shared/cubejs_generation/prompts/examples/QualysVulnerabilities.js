// Example: QualysVulnerabilities cube
cube(`QualysVulnerabilities`, {
  sql: `SELECT * FROM gold_qualys_vulnerabilities_weekly_snapshot`,
  sql_table: `gold_qualys_vulnerabilities_weekly_snapshot`,

  dimensions: {
    connectionId: {
      sql: `connection_id`,
      type: `string`,
      title: `Connection ID`,
      description: `Tenant isolation key — always filter by this`,
    },
    pk: {
      sql: `pk`,
      type: `string`,
      primaryKey: true,
    },
    hostId: {
      sql: `host_id`,
      type: `string`,
    },
    weekStart: {
      sql: `week_start`,
      type: `time`,
    },
  },

  measures: {
    criticalVulnCount: {
      sql: `critical_count`,
      type: `sum`,
      title: `Critical Vulnerabilities`,
    },
    openVulnCount: {
      sql: `open_count`,
      type: `sum`,
      title: `Open Vulnerabilities`,
    },
  },

  preAggregations: {
    weeklyByHost: {
      measures: [criticalVulnCount, openVulnCount],
      dimensions: [hostId],
      timeDimension: weekStart,
      granularity: `week`,
      refreshKey: { every: `1 day` },
    },
  },
});
