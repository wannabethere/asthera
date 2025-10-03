
WITH completion_rates AS ( SELECT a.actlabel_name AS Curriculum, COUNT(*) AS TotalActivities, SUM(CASE WHEN t.reqstatus = 'Completed' THEN 1 ELSE 0 END) AS CompletedActivities, (SUM(CASE WHEN t.reqstatus = 'Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS CompletionRate FROM tbl_tmx_userrequiredact_sumtotal t JOIN actlabel_sumtotal a ON t.activityfk = a.actlabel_pk GROUP BY a.actlabel_name) SELECT Curriculum, TotalActivities, CompletedActivities, CompletionRate FROM completion_rates ORDER BY CompletionRate DESC LIMIT 1 UNION ALL SELECT Curriculum, TotalActivities, CompletedActivities, CompletionRate FROM completion_rates ORDER BY CompletionRate ASC LIMIT 1; 

WITH completion_rates AS (
    SELECT
        a.actlabel_name AS Curriculum,
        COUNT(*) AS TotalActivities,
        SUM(CASE WHEN t.reqstatus = 'Completed' THEN 1 ELSE 0 END) AS CompletedActivities,
        (SUM(CASE WHEN t.reqstatus = 'Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS CompletionRate
    FROM
        tbl_tmx_userrequiredact_sumtotal t
    JOIN
        actlabel_sumtotal a ON t.activityfk = a.actlabel_pk
    GROUP BY
        a.actlabel_name
)
(SELECT
    Curriculum,
    TotalActivities,
    CompletedActivities,
    CompletionRate
FROM
    completion_rates
ORDER BY
    CompletionRate DESC
LIMIT 1)
UNION ALL
(SELECT
    Curriculum,
    TotalActivities,
    CompletedActivities,
    CompletionRate
FROM
    completion_rates
ORDER BY
    CompletionRate ASC
LIMIT 1);

Which curricula have the highest and lowest completion rates?
WITH completion_rates AS (
    SELECT 
        a.actlabel_name AS Curriculum,
        COUNT(*) AS TotalActivities,
        SUM(CASE WHEN t.reqstatus = 'Completed' THEN 1 ELSE 0 END) AS CompletedActivities,
        (SUM(CASE WHEN t.reqstatus = 'Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS CompletionRate
    FROM 
        tbl_tmx_userrequiredact_sumtotal t
    JOIN 
        actlabel_sumtotal a 
        ON t.activityfk = a.actlabel_pk
    GROUP BY 
        a.actlabel_name
)

-- Return the curriculum with the highest and lowest completion rates
SELECT 
    Curriculum, 
    TotalActivities, 
    CompletedActivities, 
    CompletionRate
FROM 
    completion_rates
ORDER BY 
    CompletionRate DESC
LIMIT 1

UNION ALL

SELECT 
    Curriculum, 
    TotalActivities, 
    CompletedActivities, 
    CompletionRate
FROM 
    completion_rates
ORDER BY 
    CompletionRate ASC
LIMIT 1;


SELECT TO_CHAR(plandate, 'YYYY-MM') AS enrollment_month, COUNT(CASE WHEN reqstate IN ('Assigned', 'In Progress') THEN 1 END) AS total_enrollments, COUNT(CASE WHEN reqstate = 'Completed' THEN 1 END) AS total_completions FROM tbl_tmx_userrequiredact_sumtotal WHERE plandate >= '2025-01-01' AND plandate < '2026-01-01' GROUP BY enrollment_month ORDER BY enrollment_month LIMIT 1000;

 {'documents': [{'question': 'What are the peak learning hours and days based on activity start times?', 'sql': "SELECT HOUR(a.startdt) as learning_hour, DAYNAME(a.startdt) as learning_day, COUNT(a.attempt_pk) as total_attempts, COUNT(DISTINCT a.empfk) as unique_learners, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate FROM tbl_tmx_attempt_sumtotal a WHERE a.startdt >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY) GROUP BY HOUR(a.startdt), DAYNAME(a.startdt) ORDER BY total_attempts DESC", 'instructions': 'Analyze learning time patterns to optimize course scheduling and identify peak learning periods.', 'score': 1.0557443609259778, 'sql_pair_id': 'f950863e-0f69-47f9-ac5a-74a466d784b5', 'project_id': 'sumtotal_learn'}, {'question': 'What is the learning progress distribution by user demographics (gender, company)?', 'sql': "SELECT p.gendercode, p.companyname, COUNT(DISTINCT p.personpk) as total_users, COUNT(a.attempt_pk) as total_attempts, COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) as completed_attempts, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate, ROUND(AVG(CAST(a.score AS DECIMAL)), 2) as avg_score FROM person_sumtotal p LEFT JOIN tbl_tmx_attempt_sumtotal a ON p.personpk = a.empfk WHERE p.active = 'Y' AND p.deleted = 'N' GROUP BY p.gendercode, p.companyname HAVING COUNT(DISTINCT p.personpk) >= 5 ORDER BY completion_rate DESC", 'instructions': 'Analyze learning performance by demographics to ensure equitable learning opportunities and identify potential barriers.', 'score': 1.0495377988777634, 'sql_pair_id': '5a9e9c12-dfe2-4f5e-b3cf-5a79559f1c4a', 'project_id': 'sumtotal_learn'}, {'question': 'What is the average number of attempts per user for each learning activity?', 'sql': "SELECT act.activityme as activity_name, COUNT(DISTINCT a.empfk) as unique_learners, COUNT(a.attempt_pk) as total_attempts, ROUND(COUNT(a.attempt_pk) / COUNT(DISTINCT a.empfk), 2) as avg_attempts_per_learner, COUNT(CASE WHEN a.currentattemptind = 'Y' THEN 1 END) as current_attempts, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate FROM tbl_tmx_activity_sumtotal act JOIN tbl_tmx_attempt_sumtotal a ON act.activity_pk = a.activityfk WHERE act.active = 'Y' GROUP BY act.activity_pk, act.activityme ORDER BY avg_attempts_per_learner DESC", 'instructions': 'Analyze attempt patterns to understand course difficulty and learner persistence across different activities.', 'score': 1.0495335556025476, 'sql_pair_id': '37a12d95-bb24-4253-8293-3049ab2eae47', 'project_id': 'sumtotal_learn'}, {'question': 'Which learning activities require registration and how does this affect participation?', 'sql': "SELECT CASE WHEN act.openforreg = 'Y' THEN 'Registration Required' ELSE 'No Registration Required' END as registration_status, COUNT(act.activity_pk) as total_activities, COUNT(a.attempt_pk) as total_attempts, COUNT(DISTINCT a.empfk) as unique_participants, ROUND(COUNT(a.attempt_pk) / COUNT(act.activity_pk), 2) as avg_attempts_per_activity, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate FROM tbl_tmx_activity_sumtotal act LEFT JOIN tbl_tmx_attempt_sumtotal a ON act.activity_pk = a.activityfk WHERE act.active = 'Y' GROUP BY act.openforreg ORDER BY avg_attempts_per_activity DESC", 'instructions': 'Analyze the impact of registration requirements on learning participation to optimize course accessibility.', 'score': 1.0217209784304002, 'sql_pair_id': 'cb2ab2a2-c539-4caa-8238-2d0b528bebb0', 'project_id': 'sumtotal_learn'}, {'question': 'Which learning activities have the highest launch counts and what does this indicate about popularity?', 'sql': "SELECT act.activityme as activity_name, act.code as activity_code, COUNT(a.attempt_pk) as total_attempts, ROUND(AVG(CAST(a.launchcount AS DECIMAL)), 2) as avg_launch_count, ROUND(MAX(CAST(a.launchcount AS DECIMAL)), 2) as max_launch_count, COUNT(DISTINCT a.empfk) as unique_learners, ROUND(COUNT(a.attempt_pk) / COUNT(DISTINCT a.empfk), 2) as attempts_per_learner FROM tbl_tmx_activity_sumtotal act JOIN tbl_tmx_attempt_sumtotal a ON act.activity_pk = a.activityfk WHERE act.active = 'Y' AND a.launchcount IS NOT NULL GROUP BY act.activity_pk, act.activityme, act.code ORDER BY avg_launch_count DESC, total_attempts DESC LIMIT 15", 'instructions': 'Analyze course popularity based on launch frequency to prioritize content development and resource allocation.', 'score': 1.0141771663976882, 'sql_pair_id': '703ba901-da37-4122-943a-cf21554cd343', 'project_id': 'sumtotal_learn'}, {'question': 'What are the most challenging learning activities based on low completion rates?', 'sql': "SELECT act.activityme as activity_name, act.code as activity_code, COUNT(a.attempt_pk) as total_attempts, COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) as completed_attempts, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate, ROUND(AVG(CAST(a.score AS DECIMAL)), 2) as avg_score, COUNT(CASE WHEN a.success = 'false' THEN 1 END) as failed_attempts FROM tbl_tmx_activity_sumtotal act JOIN tbl_tmx_attempt_sumtotal a ON act.activity_pk = a.activityfk WHERE act.active = 'Y' GROUP BY act.activity_pk, act.activityme, act.code HAVING COUNT(a.attempt_pk) >= 10 ORDER BY completion_rate ASC, avg_score ASC LIMIT 15", 'instructions': 'Identify challenging courses with low completion rates to prioritize content review and instructional design improvements.', 'score': 1.0123508903448053, 'sql_pair_id': 'b6678d75-a377-4aab-a90e-ed2788cfe08a', 'project_id': 'sumtotal_learn'}, {'question': 'What are the most popular learning activities and their success rates?', 'sql': "SELECT act.activityme as activity_name, act.code as activity_code, COUNT(a.attempt_pk) as total_attempts, COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) as completed_attempts, COUNT(CASE WHEN a.success = 'true' THEN 1 END) as successful_attempts, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate, ROUND(COUNT(CASE WHEN a.success = 'true' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as success_rate, ROUND(AVG(CAST(a.score AS DECIMAL)), 2) as avg_score FROM tbl_tmx_activity_sumtotal act JOIN tbl_tmx_attempt_sumtotal a ON act.activity_pk = a.activityfk WHERE act.active = 'Y' GROUP BY act.activity_pk, act.activityme, act.code ORDER BY total_attempts DESC LIMIT 15", 'instructions': 'Analyze course popularity and success rates to optimize curriculum and identify high-performing learning content.', 'score': 1.0094431337415173, 'sql_pair_id': '41161941-e308-4175-a16f-b74fedeb2567', 'project_id': 'sumtotal_learn'}, {'question': 'What is the learning activity participation pattern for users by their start date?', 'sql': "SELECT CASE WHEN p.startdate >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY) THEN 'New (30 days)' WHEN p.startdate >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY) THEN 'Recent (90 days)' WHEN p.startdate >= DATE_SUB(CURRENT_DATE, INTERVAL 365 DAY) THEN 'Mature (1 year)' ELSE 'Established (1+ years)' END as user_tenure, COUNT(DISTINCT p.personpk) as total_users, COUNT(a.attempt_pk) as total_attempts, ROUND(COUNT(a.attempt_pk) / COUNT(DISTINCT p.personpk), 2) as avg_attempts_per_user, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate FROM person_sumtotal p LEFT JOIN tbl_tmx_attempt_sumtotal a ON p.personpk = a.empfk WHERE p.active = 'Y' AND p.deleted = 'N' GROUP BY CASE WHEN p.startdate >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY) THEN 'New (30 days)' WHEN p.startdate >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY) THEN 'Recent (90 days)' WHEN p.startdate >= DATE_SUB(CURRENT_DATE, INTERVAL 365 DAY) THEN 'Mature (1 year)' ELSE 'Established (1+ years)' END ORDER BY total_users DESC", 'instructions': 'Analyze learning participation by user tenure to understand onboarding effectiveness and long-term engagement patterns.', 'score': 0.9671702352823031, 'sql_pair_id': '96024778-6898-45d5-acca-ef26366d6b20', 'project_id': 'sumtotal_learn'}, {'question': 'How many users are currently enrolled in learning activities and what is their progress status?', 'sql': "SELECT COUNT(DISTINCT a.empfk) as enrolled_users, COUNT(a.attempt_pk) as total_attempts, COUNT(CASE WHEN a.completionstatus = 'In Progress' THEN 1 END) as in_progress_attempts, COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) as completed_attempts, COUNT(CASE WHEN a.completionstatus = 'Not Started' THEN 1 END) as not_started_attempts, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate FROM tbl_tmx_attempt_sumtotal a WHERE a.currentattemptind = 'Y'", 'instructions': 'Monitor current learning status to track active learners and their progress across the platform.', 'score': 0.9337063791121639, 'sql_pair_id': '54cbf2de-2a34-4716-9733-a42629fb12e8', 'project_id': 'sumtotal_learn'}, {'question': 'How has learning activity participation changed over time by month?', 'sql': "SELECT DATE_FORMAT(a.startdt, '%Y-%m') as learning_month, COUNT(a.attempt_pk) as total_attempts, COUNT(DISTINCT a.empfk) as unique_learners, COUNT(DISTINCT a.activityfk) as unique_activities, COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) as completed_attempts, ROUND(COUNT(CASE WHEN a.completionstatus = 'Completed' THEN 1 END) * 100.0 / COUNT(a.attempt_pk), 2) as completion_rate FROM tbl_tmx_attempt_sumtotal a WHERE a.startdt >= DATE_SUB(CURRENT_DATE, INTERVAL 12 MONTH) GROUP BY DATE_FORMAT(a.startdt, '%Y-%m') ORDER BY learning_month", 'instructions': 'Track monthly learning participation trends to understand seasonal patterns and platform adoption growth.', 'score': 0.8550298226400747, 'sql_pair_id': '66326911-ccac-497e-9a82-872116390073', 'project_id': 'sumtotal_learn'}]}


