cube(`gold_users`, {
  sql: `SELECT * FROM gold_users`,
  
  title: "Gold Users",
  description: "Gold layer cube for gold_users",
  
  dimensions: {
    user_id: {
      sql: `${gold_users}.user_id`,
      type: `number`,
      title: `User Id`,
      primaryKey: true,
    },
    username: {
      sql: `${gold_users}.username`,
      type: `string`,
      title: `Username`,
    },
    email: {
      sql: `${gold_users}.email`,
      type: `string`,
      title: `Email`,
    },
    user_type: {
      sql: `${gold_users}.user_type`,
      type: `string`,
      title: `User Type`,
    },
    created_at: {
      sql: `${gold_users}.created_at`,
      type: `time`,
      title: `Created At`,
    },
    last_login: {
      sql: `${gold_users}.last_login`,
      type: `time`,
      title: `Last Login`,
    },
    is_active: {
      sql: `${gold_users}.is_active`,
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
