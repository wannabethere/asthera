cube(`silver_enrollments`, {
  sql: `SELECT * FROM silver_enrollments`,
  
  title: "Silver Enrollments",
  description: "Silver layer cube for silver_enrollments",
  
  dimensions: {
    enrollment_id: {
      sql: `${silver_enrollments}.enrollment_id`,
      type: `number`,
      title: `Enrollment Id`,
      primaryKey: true,
    },
    user_id: {
      sql: `${silver_enrollments}.user_id`,
      type: `string`,
      title: `User Id`,
    },
    course_id: {
      sql: `${silver_enrollments}.course_id`,
      type: `string`,
      title: `Course Id`,
    },
    enrolled_at: {
      sql: `${silver_enrollments}.enrolled_at`,
      type: `time`,
      title: `Enrolled At`,
    },
    completed_at: {
      sql: `${silver_enrollments}.completed_at`,
      type: `time`,
      title: `Completed At`,
    },
    status: {
      sql: `${silver_enrollments}.status`,
      type: `string`,
      title: `Status`,
    },
  },
  
  measures: {
    count: {
      sql: `1`,
      type: `count`,
      title: `Count`,
      drillMembers: [enrollment_id],
    },
    progress_percent: {
      sql: `${silver_enrollments}.progress_percent`,
      type: `sum`,
      title: `Progress Percent`,
    },
    final_grade: {
      sql: `${silver_enrollments}.final_grade`,
      type: `sum`,
      title: `Final Grade`,
    },
  },
  
  
  
  
});
