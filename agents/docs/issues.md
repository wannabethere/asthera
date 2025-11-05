Question:
Who are the top learners this quarter on the team managed by managerId 11555?

dataset: Sumtotal


SQL Query:

SELECT ju.personfk, COUNT(pr.personfk) as learning_count FROM jobuser_sumtotal ju JOIN personrelation_sumtotal pr ON ju.personfk = pr.personfk WHERE pr.manager1fk = 11555 AND pr.createddate_ts >= DATE_TRUNC('quarter', CURRENT_DATE) GROUP BY ju.personfk ORDER BY learning_count DESC;

Result:
No data returned from summarization pipeline

Issue: Query is wrong because of picking wrong tables. correct tables are personrelation_sumtotal, TBL_TMX_Attempt_sumtotal.

---------------------------------------------------------------------------------------------------
Question
what are the top 5 Activities that has high average time spent by learners??

dataset: Sumtotal

SQL Query:

SELECT act.activityme as activity_name, ROUND(AVG(CAST(a.elapsedseconds AS DECIMAL) / 60), 2) as avg_minutes_spent FROM tbl_tmx_activity_sumtotal act JOIN tbl_tmx_attempt_sumtotal a ON act.activity_pk = a.activityfk WHERE a.elapsedseconds IS NOT NULL AND a.elapsedseconds > 0 GROUP BY act.activity_pk, act.activityme ORDER BY avg_minutes_spent DESC LIMIT 5;


Result:
No data returned from summarization pipeline

Issue: Here column name Activityme is wrong. correct column name is activityname.

-----------------------------------------------------------------------------------------------------
Question
How many active employees have more than one overdue compliance item?

dataset: cornerstone learn

SQL Query:

SELECT COUNT(DISTINCT u.userId) FROM User_csod u JOIN Transcript_csod t ON u.userId = t.userID WHERE u.userStatus = 'active' AND t.isOverdue = 'true' GROUP BY t.userID HAVING COUNT(t.isOverdue) > 1;

Result:
No data returned from summarization pipeline

Issue: The given Sql query is wrong because user asked KPI count so we don't need group by and we need to use lower when match exact string.
------------------------------------------------------------------------------------------------------

Question:
How has the total number of overdue compliance assignments trended over the past six months?

dataset: cornerstone learn

SQL Query:

SELECT COUNT(*) FROM Transcript_csod AS t JOIN Activity_csod AS a ON t.loID = a.loID WHERE lower(t.isOverdue) = lower('true') AND lower(a.isCompliance) = lower('true') AND a.activityEndDate >= CAST('2025-05-04 00:00:00' AS TIMESTAMP WITH TIME ZONE);

Result: 0

Issue: The given sql query is wrong and picking wrong columns because first it needs to take last 6 months for all overdue assignments using due date column and then check for compliance and give us the line chart.
------------------------------------------------------------------------------------------------------
Question
On average, how many days late are our overdue compliance assignments?

dataset: cornerstone learn

SQL Query:

SELECT AVG(CAST(CURRENT_DATE - CAST(a.activityEndDate AS DATE) AS INTEGER)) AS average_days_late FROM Transcript_csod AS t JOIN Activity_csod AS a ON t.loID = a.loID WHERE lower(t.isOverdue) = 'true' AND lower(a.isCompliance) = 'true';

Result: None

Issue: The given sql query is wrong and picking wrong columns. here we need to calcutate the late days by today date and duedate.

------------------------------------------------------------------------------------------------------
Question
How many compliance certifications are set to expire in the coming quarter?

dataset: cornerstone learn

SQL Query:
SELECT COUNT(t.loID) FROM Transcript_csod AS t JOIN Activity_csod AS a ON t.loID = a.loID WHERE lower(a.isCompliance) = lower('true') AND t.expiryDate >= CAST('2025-12-01 00:00:00' AS TIMESTAMP WITH TIME ZONE) AND t.expiryDate < CAST('2026-03-01 00:00:00' AS TIMESTAMP WITH TIME ZONE);

Result: KPI - 4

Issue: The query is wrong. it needs to take is certification also.

------------------------------------------------------------------------------------------------------
Question
How many unique employees have engaged with any training in the past month?

dataset: cornerstone learn

SQL Query:
SELECT COUNT(DISTINCT t.userID) FROM Transcript_csod AS t JOIN Activity_csod AS a ON t.userID = t.userID WHERE a.activityStartDate >= CAST('2025-10-04 00:00:00' AS TIMESTAMP WITH TIME ZONE);

Result: KPI with 29k

Issue: The query is incorrect because here we don't need activity table and it needs to take attempt startdate which stores when the user launched the activity. It take cartesian join but we don't need that.
------------------------------------------------------------------------------------------------------
Question
What is the cumulative time, in hours, that the organization has spent on learning this year?

dataset: cornerstone learn

SQL Query:
SELECT SUM(t.timeSpent) AS cumulative_time_spent FROM Transcript_csod AS t JOIN Activity_csod AS a ON t.loID = a.loID WHERE a.activityStartDate >= CAST('2025-01-01 00:00:00' AS TIMESTAMP WITH TIME ZONE) AND a.activityStartDate < CAST('2026-01-01 00:00:00' AS TIMESTAMP WITH TIME ZONE);

Result: KPI None

Issue: The query is not correct. It picked wrong columns. when the activity is completed then only it has timespent value. so it needs to take completion date.
------------------------------------------------------------------------------------------------------

"query": "What are our top 5 most popular courses right now based on completion rates?",
  "project_id": "cornerstone_learning",
  
   "sql": "SELECT act.activityName, COUNT(CASE WHEN trans.isCompleted = 'true' THEN 1 END) * 1.0 / COUNT(trans.userID) AS completion_rate FROM Transcript_csod AS trans JOIN Activity_csod AS act ON trans.loID = act.loID GROUP BY act.activityName ORDER BY completion_rate DESC LIMIT 5;",
  "query": "What are our top 5 most popular courses right now based on completion rates?",
  "project_id": "cornerstone_learning",
  "data_description": "Corner stone learning",
