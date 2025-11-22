# lms_analytics - Data Model Documentation

**Generated**: 2025-11-21 13:46:03

## Overview

Learning management system analytics

## Architecture

This data model follows the medallion architecture:

```
Raw Layer → Silver Layer → Gold Layer
```

### Raw Layer
Source tables with minimal transformation:

- `users`
- `courses`
- `enrollments`

### Silver Layer
Cleaned, deduplicated, and conformed data

#### Silver Table Analysis
Collected requirements for 3 tables:

- **users**:
  - Analysis Types: descriptive, diagnostic, predictive, exploratory, segmentation, cohort, funnel
  - Business Goals: 6 goals
- **courses**:
  - Analysis Types: descriptive, diagnostic, exploratory, comparative
  - Business Goals: 5 goals
- **enrollments**:
  - Analysis Types: descriptive, diagnostic, predictive, prescriptive, exploratory, comparative, trend, segmentation, cohort, funnel
  - Business Goals: 7 goals

### Gold Layer
Business-level aggregations and metrics

## Data Marts

Planned 3 data mart(s):

### Data Mart 1: Create learner engagement analytics dashboard

**Complexity**: medium

**Marts**:
- **learner_engagement_summary**: This mart contains a summary of learner engagement metrics, including total courses enrolled, average course duration, and total courses completed per user.
  - Question: How many courses has each user enrolled in, and what is their average course duration and completion rate?
  - Grain: One row per user.
- **course_performance_summary**: This mart contains performance metrics for each course, including total enrollments, total completions, and average completion time.
  - Question: What are the total enrollments and completion rates for each course offered?
  - Grain: One row per course.
- **user_acquisition_retention_analysis**: This mart contains metrics related to user acquisition and retention, including the number of courses enrolled and the number of days since registration.
  - Question: How many courses have users enrolled in since their registration, and how long have they been registered?
  - Grain: One row per user.

### Data Mart 2: Build course performance metrics data mart

**Complexity**: medium

**Marts**:
- **course_performance_metrics**: This mart contains metrics related to course performance, including total enrollments, average completion rates, and total duration of courses.
  - Question: What are the performance metrics for each course, including total enrollments and average completion rates?
  - Grain: One row per course.
- **user_engagement_metrics**: This mart contains metrics related to user engagement, including total courses enrolled, average completion rates, and total time spent by users.
  - Question: How engaged are users based on their course enrollments and completion rates?
  - Grain: One row per user.
- **enrollment_trends**: This mart contains trends in enrollments over time, including total enrollments and the number of courses offered on each date.
  - Question: What are the trends in course enrollments over time?
  - Grain: One row per enrollment date.

### Data Mart 3: Generate instructor analytics summary

**Complexity**: medium

**Marts**:
- **instructor_engagement_summary**: This mart contains a summary of instructor engagement metrics, including total courses enrolled, average course duration, and total courses completed by each user.
  - Question: What is the total number of courses each user has enrolled in, along with the average duration of those courses and the number of courses they have completed?
  - Grain: One row per user.
- **course_performance_summary**: This mart contains a summary of course performance metrics, including total enrollments and completion rates for each course.
  - Question: How many students are enrolled in each course, and what is the completion rate for those courses?
  - Grain: One row per course.
- **user_acquisition_retention_summary**: This mart contains a summary of user acquisition and retention metrics, including total courses enrolled and the number of days users have engaged with courses.
  - Question: What is the total number of courses each user has enrolled in, and how many days have they engaged with the courses?
  - Grain: One row per user.

## MDL Schema (Single Source of Truth)

The complete MDL schema is available at: `mdl/lms_analytics_schema.json`

This schema contains:
- **Models**: 3 models across raw, silver, and gold layers
- **Relationships**: 2 relationships
- **Metrics**: 8 metrics
- **Views**: 0 views
- **Transformations**: 40 transformations
- **Governance**: Data quality rules, compliance requirements, lineage

All target formats (Cube.js, dbt) are generated from this MDL schema.

## Generated Artifacts

### Cubes (Generated from MDL)
- `cubes/raw/users.json`
- `cubes/raw/users.js`
- `cubes/raw/courses.json`
- `cubes/raw/courses.js`
- `cubes/raw/enrollments.json`
- `cubes/raw/enrollments.js`
- `cubes/silver/users.json`
- `cubes/silver/users.js`
- `cubes/silver/courses.json`
- `cubes/silver/courses.js`
- ... and 8 more

### Transformations
- `transformations/raw_to_silver/users.json`
- `transformations/raw_to_silver/courses.json`
- `transformations/raw_to_silver/enrollments.json`
- `transformations/silver_to_gold/users.json`
- `transformations/silver_to_gold/courses.json`
- `transformations/silver_to_gold/enrollments.json`
- `transformations/silver_to_gold/gold_total_learners_this_year.sql`
- `transformations/silver_to_gold/gold_total_learners_this_year.json`
- `transformations/silver_to_gold/gold_total_learners_last_year.sql`
- `transformations/silver_to_gold/gold_total_learners_last_year.json`
- `transformations/silver_to_gold/gold_percentage_change_learners.sql`
- `transformations/silver_to_gold/gold_percentage_change_learners.json`
- `transformations/silver_to_gold/gold_enrollment_count.sql`
- `transformations/silver_to_gold/gold_enrollment_count.json`
- `transformations/silver_to_gold/gold_completion_count.sql`
- `transformations/silver_to_gold/gold_completion_count.json`
- `transformations/silver_to_gold/gold_enrollment_completion_rate.sql`
- `transformations/silver_to_gold/gold_enrollment_completion_rate.json`
- `transformations/silver_to_gold/gold_enrollment_completion_rate_trend.sql`
- `transformations/silver_to_gold/gold_enrollment_completion_rate_trend.json`
- `transformations/silver_to_gold/gold_active_learners_count.sql`
- `transformations/silver_to_gold/gold_active_learners_count.json`
- `transformations/silver_to_gold/gold_active_learners_by_user_type.sql`
- `transformations/silver_to_gold/gold_active_learners_by_user_type.json`
- `transformations/silver_to_gold/gold_active_learners_daily_trend.sql`
- `transformations/silver_to_gold/gold_active_learners_daily_trend.json`
- `transformations/silver_to_gold/gold_average_time_to_completion.sql`
- `transformations/silver_to_gold/gold_average_time_to_completion.json`
- `transformations/silver_to_gold/gold_average_time_to_completion_last_year.sql`
- `transformations/silver_to_gold/gold_average_time_to_completion_last_year.json`
- `transformations/silver_to_gold/gold_comparison_average_time_to_completion.sql`
- `transformations/silver_to_gold/gold_comparison_average_time_to_completion.json`
- `transformations/silver_to_gold/gold_students_completed_courses.sql`
- `transformations/silver_to_gold/gold_students_completed_courses.json`
- `transformations/silver_to_gold/gold_total_students_enrolled.sql`
- `transformations/silver_to_gold/gold_total_students_enrolled.json`
- `transformations/silver_to_gold/gold_percentage_completed_courses.sql`
- `transformations/silver_to_gold/gold_percentage_completed_courses.json`
- `transformations/silver_to_gold/gold_quarterly_trend_percentage_completed_courses.sql`
- `transformations/silver_to_gold/gold_quarterly_trend_percentage_completed_courses.json`
- `transformations/silver_to_gold/gold_average_progress_percentage.sql`
- `transformations/silver_to_gold/gold_average_progress_percentage.json`
- `transformations/silver_to_gold/gold_average_progress_percentage_by_course.sql`
- `transformations/silver_to_gold/gold_average_progress_percentage_by_course.json`
- `transformations/silver_to_gold/gold_average_progress_percentage_by_enrollment_status.sql`
- `transformations/silver_to_gold/gold_average_progress_percentage_by_enrollment_status.json`
- `transformations/silver_to_gold/gold_total_learners.sql`
- `transformations/silver_to_gold/gold_total_learners.json`
- `transformations/silver_to_gold/gold_average_engagement_time.sql`
- `transformations/silver_to_gold/gold_average_engagement_time.json`
- `transformations/silver_to_gold/gold_engagement_growth_rate.sql`
- `transformations/silver_to_gold/gold_engagement_growth_rate.json`
- `transformations/silver_to_gold/gold_engagement_by_category.sql`
- `transformations/silver_to_gold/gold_engagement_by_category.json`
- `transformations/silver_to_gold/gold_percentage_of_active_learners.sql`
- `transformations/silver_to_gold/gold_percentage_of_active_learners.json`
- `transformations/silver_to_gold/gold_engagement_trend.sql`
- `transformations/silver_to_gold/gold_engagement_trend.json`
- `transformations/silver_to_gold/gold_total_courses_offered.sql`
- `transformations/silver_to_gold/gold_total_courses_offered.json`
- `transformations/silver_to_gold/gold_average_course_rating.sql`
- `transformations/silver_to_gold/gold_average_course_rating.json`
- `transformations/silver_to_gold/gold_total_enrollments.sql`
- `transformations/silver_to_gold/gold_total_enrollments.json`
- `transformations/silver_to_gold/gold_course_completion_rate.sql`
- `transformations/silver_to_gold/gold_course_completion_rate.json`
- `transformations/silver_to_gold/gold_enrollment_growth_rate.sql`
- `transformations/silver_to_gold/gold_enrollment_growth_rate.json`
- `transformations/silver_to_gold/gold_average_time_to_complete.sql`
- `transformations/silver_to_gold/gold_average_time_to_complete.json`
- `transformations/silver_to_gold/gold_course_performance_trend.sql`
- `transformations/silver_to_gold/gold_course_performance_trend.json`
- `transformations/silver_to_gold/gold_total_instructors_count.sql`
- `transformations/silver_to_gold/gold_total_instructors_count.json`
- `transformations/silver_to_gold/gold_average_instructor_rating.sql`
- `transformations/silver_to_gold/gold_average_instructor_rating.json`
- `transformations/silver_to_gold/gold_instructor_courses_count.sql`
- `transformations/silver_to_gold/gold_instructor_courses_count.json`
- `transformations/silver_to_gold/gold_instructor_attendance_rate.sql`
- `transformations/silver_to_gold/gold_instructor_attendance_rate.json`
- `transformations/silver_to_gold/gold_instructor_feedback_count.sql`
- `transformations/silver_to_gold/gold_instructor_feedback_count.json`
- `transformations/silver_to_gold/gold_instructor_salary_sum.sql`
- `transformations/silver_to_gold/gold_instructor_salary_sum.json`
- `transformations/silver_to_gold/gold_instructor_growth_rate.sql`
- `transformations/silver_to_gold/gold_instructor_growth_rate.json`

### SQL Scripts
- `sql/raw_to_silver/users.sql`
- `sql/raw_to_silver/courses.sql`
- `sql/raw_to_silver/enrollments.sql`
- `sql/silver_to_gold/users.sql`
- `sql/silver_to_gold/courses.sql`
- `sql/silver_to_gold/enrollments.sql`
- `data_marts/learner_engagement_summary.sql`
- `data_marts/course_performance_summary.sql`
- `data_marts/user_acquisition_retention_analysis.sql`
- `data_marts/course_performance_metrics.sql`
- `data_marts/user_engagement_metrics.sql`
- `data_marts/enrollment_trends.sql`
- `data_marts/instructor_engagement_summary.sql`
- `data_marts/course_performance_summary.sql`
- `data_marts/user_acquisition_retention_summary.sql`
- `data_marts/learner_engagement_summary_enhanced.sql`
- `data_marts/course_performance_summary_enhanced.sql`
- `data_marts/user_acquisition_retention_analysis_enhanced.sql`
- `data_marts/course_performance_metrics_enhanced.sql`
- `data_marts/user_engagement_metrics_enhanced.sql`
- `data_marts/enrollment_trends_enhanced.sql`
- `data_marts/instructor_engagement_summary_enhanced.sql`
- `data_marts/course_performance_summary_enhanced.sql`
- `data_marts/user_acquisition_retention_summary_enhanced.sql`

### Data Marts
- `data_marts/data_mart_plan_1.json`
- `data_marts/data_mart_plan_2.json`
- `data_marts/data_mart_plan_3.json`

## Usage

1. Review generated Cube.js definitions in `cubes/`
2. Execute transformation SQL in `sql/` in order
3. Review data mart SQL in `data_marts/`
4. Deploy cube definitions to your Cube.js instance
5. Configure pre-aggregations based on query patterns

## Next Steps

1. Validate SQL transformations
2. Test cube definitions
3. Execute data mart SQL queries
4. Configure refresh schedules
5. Set up data quality monitoring
