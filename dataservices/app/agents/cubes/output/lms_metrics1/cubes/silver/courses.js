cube(`silver_courses`, {
  sql: `SELECT * FROM silver_courses`,
  
  title: "Silver Courses",
  description: "Silver layer cube for silver_courses",
  
  dimensions: {
    course_id: {
      sql: `${silver_courses}.course_id`,
      type: `number`,
      title: `Course Id`,
      primaryKey: true,
    },
    course_name: {
      sql: `${silver_courses}.course_name`,
      type: `string`,
      title: `Course Name`,
    },
    course_code: {
      sql: `${silver_courses}.course_code`,
      type: `string`,
      title: `Course Code`,
    },
    instructor_id: {
      sql: `${silver_courses}.instructor_id`,
      type: `string`,
      title: `Instructor Id`,
    },
    category: {
      sql: `${silver_courses}.category`,
      type: `string`,
      title: `Category`,
    },
    difficulty_level: {
      sql: `${silver_courses}.difficulty_level`,
      type: `string`,
      title: `Difficulty Level`,
    },
    created_at: {
      sql: `${silver_courses}.created_at`,
      type: `time`,
      title: `Created At`,
    },
  },
  
  measures: {
    count: {
      sql: `1`,
      type: `count`,
      title: `Count`,
      drillMembers: [course_id],
    },
    duration_hours: {
      sql: `${silver_courses}.duration_hours`,
      type: `sum`,
      title: `Duration Hours`,
    },
  },
  
  
  
  
});
