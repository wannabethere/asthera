cube(`gold_enrollments`, {
  sql: `SELECT * FROM gold_enrollments`,
  
  title: "Gold Enrollments",
  description: "Gold layer cube for gold_enrollments",
  
  dimensions: {
    enrollment_id: {
      sql: `${gold_enrollments}.enrollment_id`,
      type: `number`,
      title: `Enrollment Id`,
      primaryKey: true,
    },
    user_id: {
      sql: `${gold_enrollments}.user_id`,
      type: `string`,
      title: `User Id`,
    },
    course_id: {
      sql: `${gold_enrollments}.course_id`,
      type: `string`,
      title: `Course Id`,
    },
    enrolled_at: {
      sql: `${gold_enrollments}.enrolled_at`,
      type: `time`,
      title: `Enrolled At`,
    },
    completed_at: {
      sql: `${gold_enrollments}.completed_at`,
      type: `time`,
      title: `Completed At`,
    },
    status: {
      sql: `${gold_enrollments}.status`,
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
      sql: `${gold_enrollments}.progress_percent`,
      type: `sum`,
      title: `Progress Percent`,
    },
    final_grade: {
      sql: `${gold_enrollments}.final_grade`,
      type: `sum`,
      title: `Final Grade`,
    },
  },
  
  
  
  
});
