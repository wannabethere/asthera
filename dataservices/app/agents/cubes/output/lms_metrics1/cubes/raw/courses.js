cube(`raw_courses`, {
  sql: `SELECT * FROM raw_courses`,
  
  title: "Raw Courses",
  description: "Raw layer cube for raw_courses",
  
  dimensions: {
    course_id: {
      sql: `${raw_courses}.course_id`,
      type: `number`,
      title: `Course Id`,
      primaryKey: true,
    },
    course_name: {
      sql: `${raw_courses}.course_name`,
      type: `string`,
      title: `Course Name`,
    },
    course_code: {
      sql: `${raw_courses}.course_code`,
      type: `string`,
      title: `Course Code`,
    },
    instructor_id: {
      sql: `${raw_courses}.instructor_id`,
      type: `string`,
      title: `Instructor Id`,
    },
    category: {
      sql: `${raw_courses}.category`,
      type: `string`,
      title: `Category`,
    },
    difficulty_level: {
      sql: `${raw_courses}.difficulty_level`,
      type: `string`,
      title: `Difficulty Level`,
    },
    created_at: {
      sql: `${raw_courses}.created_at`,
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
      sql: `${raw_courses}.duration_hours`,
      type: `sum`,
      title: `Duration Hours`,
    },
  },
  
  
  
  
});
