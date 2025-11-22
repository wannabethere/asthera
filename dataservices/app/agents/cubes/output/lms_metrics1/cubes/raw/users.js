cube(`raw_users`, {
  sql: `SELECT * FROM raw_users`,
  
  title: "Raw Users",
  description: "Raw layer cube for raw_users",
  
  dimensions: {
    user_id: {
      sql: `${raw_users}.user_id`,
      type: `number`,
      title: `User Id`,
      primaryKey: true,
    },
    username: {
      sql: `${raw_users}.username`,
      type: `string`,
      title: `Username`,
    },
    email: {
      sql: `${raw_users}.email`,
      type: `string`,
      title: `Email`,
    },
    user_type: {
      sql: `${raw_users}.user_type`,
      type: `string`,
      title: `User Type`,
    },
    created_at: {
      sql: `${raw_users}.created_at`,
      type: `time`,
      title: `Created At`,
    },
    last_login: {
      sql: `${raw_users}.last_login`,
      type: `time`,
      title: `Last Login`,
    },
    is_active: {
      sql: `${raw_users}.is_active`,
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
