cube(`gold_courses`, {
  sql: `SELECT * FROM gold_courses`,
  
  title: "Gold Courses",
  description: "Gold layer cube for gold_courses",
  
  dimensions: {
    course_id: {
      sql: `${gold_courses}.course_id`,
      type: `number`,
      title: `Course Id`,
      primaryKey: true,
    },
    course_name: {
      sql: `${gold_courses}.course_name`,
      type: `string`,
      title: `Course Name`,
    },
    course_code: {
      sql: `${gold_courses}.course_code`,
      type: `string`,
      title: `Course Code`,
    },
    instructor_id: {
      sql: `${gold_courses}.instructor_id`,
      type: `string`,
      title: `Instructor Id`,
    },
    category: {
      sql: `${gold_courses}.category`,
      type: `string`,
      title: `Category`,
    },
    difficulty_level: {
      sql: `${gold_courses}.difficulty_level`,
      type: `string`,
      title: `Difficulty Level`,
    },
    created_at: {
      sql: `${gold_courses}.created_at`,
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
      sql: `${gold_courses}.duration_hours`,
      type: `sum`,
      title: `Duration Hours`,
    },
  },
  
  
  
  
});
