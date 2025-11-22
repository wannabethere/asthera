cube(`silver_users`, {
  sql: `SELECT * FROM silver_users`,
  
  title: "Silver Users",
  description: "Silver layer cube for silver_users",
  
  dimensions: {
    user_id: {
      sql: `${silver_users}.user_id`,
      type: `number`,
      title: `User Id`,
      primaryKey: true,
    },
    username: {
      sql: `${silver_users}.username`,
      type: `string`,
      title: `Username`,
    },
    email: {
      sql: `${silver_users}.email`,
      type: `string`,
      title: `Email`,
    },
    user_type: {
      sql: `${silver_users}.user_type`,
      type: `string`,
      title: `User Type`,
    },
    created_at: {
      sql: `${silver_users}.created_at`,
      type: `time`,
      title: `Created At`,
    },
    last_login: {
      sql: `${silver_users}.last_login`,
      type: `time`,
      title: `Last Login`,
    },
    is_active: {
      sql: `${silver_users}.is_active`,
      type: `string`,
      title: `Is Active`,
    },
  },
  
  measures: {
    count: {
      sql: `1`,
      type: `count`,
      title: `Count`,
      drillMembers: [user_id],
    },
  },
  
  
  
  
});
