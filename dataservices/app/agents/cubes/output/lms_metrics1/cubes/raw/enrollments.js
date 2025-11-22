cube(`raw_enrollments`, {
  sql: `SELECT * FROM raw_enrollments`,
  
  title: "Raw Enrollments",
  description: "Raw layer cube for raw_enrollments",
  
  dimensions: {
    enrollment_id: {
      sql: `${raw_enrollments}.enrollment_id`,
      type: `number`,
      title: `Enrollment Id`,
      primaryKey: true,
    },
    user_id: {
      sql: `${raw_enrollments}.user_id`,
      type: `string`,
      title: `User Id`,
    },
    course_id: {
      sql: `${raw_enrollments}.course_id`,
      type: `string`,
      title: `Course Id`,
    },
    enrolled_at: {
      sql: `${raw_enrollments}.enrolled_at`,
      type: `time`,
      title: `Enrolled At`,
    },
    completed_at: {
      sql: `${raw_enrollments}.completed_at`,
      type: `time`,
      title: `Completed At`,
    },
    status: {
      sql: `${raw_enrollments}.status`,
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
      sql: `${raw_enrollments}.progress_percent`,
      type: `sum`,
      title: `Progress Percent`,
    },
    final_grade: {
      sql: `${raw_enrollments}.final_grade`,
      type: `sum`,
      title: `Final Grade`,
    },
  },
  
  
  
  
});
