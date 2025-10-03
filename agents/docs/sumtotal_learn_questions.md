Questions for Sumtotal Learn Data 

Q1. What is my team's overall compliance rate for mandatory training due this quarter? 

SQL Query: 

SELECT (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS ComplianceRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN PersonRelation_sumtotal pr ON ura.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND ura.DueDate BETWEEN DATE_TRUNC('quarter', NOW()) AND DATE_TRUNC('quarter', NOW()) + INTERVAL '3 months' - INTERVAL '1 day'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q2. Which of my direct reports have overdue training, and what are the specific courses? 

SQL Query: 

SELECT p.FullName, act.Activityme, ura.DueDate, (CURRENT_DATE - ura.DueDate::date) AS DaysOverdue FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND ura.IsSatisfied = 0 AND ura.DueDate < CURRENT_DATE; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q3. What is the completion status of the onboarding curriculum for my new hires (joined in the last 90 days)? 

SQL Query: 

SELECT p.FullName, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.ActivityFK)) * 100 AS OnboardingProgress FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND p.StartDate >= NOW() - INTERVAL '90 days' AND ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Onboarding%') GROUP BY p.FullName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q4. Who are the top learners on my team based on the number of courses completed this quarter? 

SQL Query: 

SELECT p.FullName, COUNT(att.Attempt_PK) AS CoursesCompleted FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.CompletionStatus = 'Completed' AND att.EndDt >= DATE_TRUNC('quarter', NOW()) GROUP BY p.FullName ORDER BY CoursesCompleted DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q5. What is the average assessment score for my team on key courses compared to the company average? 

SQL Query: 

SELECT act.Activityme, 'My Team' AS Category, AVG(att.Score::numeric) AS AverageScore FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON att.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND act.Activityme IN ('Critical Course A', 'Critical Course B') GROUP BY act.Activityme UNION ALL SELECT act.Activityme, 'Company' AS Category, AVG(att.Score::numeric) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE act.Activityme IN ('Critical Course A', 'Critical Course B') GROUP BY act.Activityme; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q6. Which certifications held by my team members are expiring in the next 90 days? 

SQL Query: 

SELECT p.FullName, act.Activityme, ura.ExpirationDate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND ura.IsCertification = 1 AND ura.ExpirationDate BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days'; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q7. What are the most popular elective (non-required) courses my team is taking? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Enrollments FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON att.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.ActivityFK NOT IN (SELECT ActivityFK FROM TBL_TMX_UserRequiredAct_sumtotal WHERE EmpFK = att.EmpFK) GROUP BY act.Activityme ORDER BY Enrollments DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q8. How many training hours has each of my team members logged this month? 

SQL Query: 

SELECT p.FullName, SUM(att.ElapsedSeconds::numeric)/3600.0 AS HoursLogged FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.EndDt >= DATE_TRUNC('month', NOW()) GROUP BY p.FullName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q9. What is my team's first-attempt pass rate on compliance quizzes? 

SQL Query: 

WITH FirstAttempts AS (SELECT EmpFK, ActivityFK, MIN(StartDt) as FirstStart FROM TBL_TMX_Attempt_sumtotal GROUP BY EmpFK, ActivityFK) SELECT COUNT(CASE WHEN att.Success = 'Passed' THEN 1 END) * 100.0 / COUNT(att.Attempt_PK) FROM TBL_TMX_Attempt_sumtotal att JOIN FirstAttempts fa ON att.EmpFK = fa.EmpFK AND att.StartDt = fa.FirstStart JOIN PersonRelation_sumtotal pr ON att.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Compliance%'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q10. Are there any skill gaps on my team for a specific required skill/course (e.g., 'Advanced Excel')? 

SQL Query: 

SELECT p.FullName FROM Person_sumtotal p JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND p.PersonPK NOT IN (SELECT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed' AND ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme = 'Advanced Excel')); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q11. What is the trend of my team's course completions over the last 6 months? 

SQL Query: 

SELECT TO_CHAR(att.EndDt, 'YYYY-MM') AS Month, COUNT(att.Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal att JOIN PersonRelation_sumtotal pr ON att.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.CompletionStatus = 'Completed' AND att.EndDt >= NOW() - INTERVAL '6 months' GROUP BY Month ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q12. How does my team's training activity this quarter compare to last quarter? 

SQL Query: 

SELECT 'This Quarter' AS Period, COUNT(Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal WHERE EmpFK IN (SELECT PersonFK FROM PersonRelation_sumtotal WHERE Manager1FK = [Current_Manager_ID]) AND EndDt >= DATE_TRUNC('quarter', NOW()) UNION ALL SELECT 'Last Quarter' AS Period, COUNT(Attempt_PK) FROM TBL_TMX_Attempt_sumtotal WHERE EmpFK IN (SELECT PersonFK FROM PersonRelation_sumtotal WHERE Manager1FK = [Current_Manager_ID]) AND EndDt BETWEEN DATE_TRUNC('quarter', NOW()) - INTERVAL '3 months' AND DATE_TRUNC('quarter', NOW()) - INTERVAL '1 day'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric_with_comparison 

 

Q13. What is the completion status of the 'Annual Ethics Refresher' for all my direct reports? 

SQL Query: 

SELECT CASE WHEN ura.IsSatisfied = 1 THEN 'Completed' ELSE 'Pending' END AS Status, COUNT(ura.EmpFK) AS EmployeeCount FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN PersonRelation_sumtotal pr ON ura.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme = 'Annual Ethics Refresher') GROUP BY Status; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q14. Which of my team members have failed an assessment more than once in the last 30 days? 

SQL Query: 

SELECT p.FullName, act.Activityme, COUNT(att.Attempt_PK) AS Failures FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.Success = 'Failed' AND att.EndDt >= NOW() - INTERVAL '30 days' GROUP BY p.FullName, act.Activityme HAVING COUNT(att.Attempt_PK) > 1; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q15. What is the total training cost associated with my team's learning activities this year? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) AS TeamTrainingCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON att.EmpFK = pr.PersonFK WHERE pr.Manager1FK = [Current_Manager_ID] AND att.StartDt >= DATE_TRUNC('year', NOW()); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q16. What are the top 10 most completed courses this quarter, and what is their average success score? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Completions, AVG(att.Score::numeric) AS AverageScore FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus = 'Completed' AND att.EndDt >= DATE_TRUNC('quarter', NOW()) GROUP BY act.Activityme ORDER BY Completions DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q17. What is the month-over-month trend of course enrollments versus completions for the current fiscal year? 

SQL Query: 

SELECT TO_CHAR(att.StartDt, 'YYYY-MM') AS Month, COUNT(att.Attempt_PK) AS Enrollments, COUNT(CASE WHEN att.CompletionStatus = 'Completed' THEN 1 END) AS Completions FROM TBL_TMX_Attempt_sumtotal att WHERE att.StartDt >= DATE_TRUNC('year', NOW()) GROUP BY Month ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q18. Which curricula have the highest and lowest completion rates? 

SQL Query: 

SELECT c.Activityme AS CurriculumName, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS CompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal a ON ura.ActivityFK = a.Activity_PK JOIN TBL_TMX_Activity_sumtotal c ON a.PrntActFK = c.Activity_PK JOIN Actlabel_sumtotal al ON c.ActivityLabelFK = al.ActLabel_PK WHERE al.ActLabel_Name = 'Curriculum' GROUP BY CurriculumName ORDER BY CompletionRate DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q19. What is the average time (in days) it takes for a user to complete a course after it has been assigned? 

SQL Query: 

SELECT AVG(att.EndDt::date - ura.PlanDate::date) AS AvgDaysToComplete FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON att.EmpFK = ura.EmpFK AND att.ActivityFK = ura.ActivityFK WHERE att.CompletionStatus = 'Completed'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q20. What is the distribution of activity types (E-Course, ILT Class, Micro-video, Document) across our entire training catalog? 

SQL Query: 

SELECT al.ActLabel_Name, COUNT(act.Activity_PK) AS CountOfActivities FROM TBL_TMX_Activity_sumtotal act JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK GROUP BY al.ActLabel_Name ORDER BY CountOfActivities DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: donut 

 

Q21. Which 5 activities have the highest number of 'Failed' attempts, and who are the primary job roles taking them? 

SQL Query: 

SELECT act.Activityme, ju.JobName, COUNT(att.Attempt_PK) AS FailedAttempts FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK WHERE att.Success = 'Failed' AND ju.IsPrimary = 1 GROUP BY act.Activityme, ju.JobName ORDER BY FailedAttempts DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q22. What is the average number of attempts required to pass compliance-related assessments? 

SQL Query: 

WITH AttemptCounts AS (SELECT EmpFK, ActivityFK, COUNT(Attempt_PK) AS Attempts FROM TBL_TMX_Attempt_sumtotal WHERE Success = 'Passed' AND ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Compliance%') GROUP BY EmpFK, ActivityFK) SELECT AVG(Attempts) FROM AttemptCounts; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q23. How does the average user score on key certification exams vary by the user's primary organization? 

SQL Query: 

SELECT o.VEme AS OrganizationName, AVG(att.Score::numeric) AS AverageScore FROM TBL_TMX_Attempt_sumtotal att JOIN PersonOrganization_sumtotal po ON att.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE po.IsPrimary = 1 AND att.ActivityFK IN (SELECT ActivityFK FROM TBL_TMX_UserRequiredAct_sumtotal WHERE IsCertification = 1) GROUP BY OrganizationName ORDER BY AverageScore DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q24. What are the most popular training activities (by unique user attempts) for employees who started in the last 6 months? 

SQL Query: 

SELECT act.Activityme, COUNT(DISTINCT att.EmpFK) AS UniqueLearners FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE p.StartDate >= NOW() - INTERVAL '6 months' GROUP BY act.Activityme ORDER BY UniqueLearners DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q25. Which training activities show the highest drop-off rate (i.e., started but never completed)? 

SQL Query: 

SELECT act.Activityme, COUNT(CASE WHEN att.CompletionStatus <> 'Completed' THEN 1 END) * 100.0 / COUNT(att.Attempt_PK) AS DropOffRate FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK GROUP BY act.Activityme HAVING COUNT(att.Attempt_PK) > 50 ORDER BY DropOffRate DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q26. What is the total estimated training time (in hours) assigned across the entire organization this year? 

SQL Query: 

SELECT SUM(act.EstDur::numeric) / 3600.0 AS TotalAssignedHours FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.PlanDate >= DATE_TRUNC('year', NOW()); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q27. Which ILT (Instructor-Led Training) classes consistently have the lowest attendance relative to their maximum capacity? 

SQL Query: 

SELECT act.Activityme, (COUNT(att.EmpFK) * 100.0 / act.MaxCapacity::numeric) AS FillRate FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK WHERE al.ActLabel_Name = 'ILT Class' AND act.MaxCapacity::numeric > 0 GROUP BY act.Activityme, act.MaxCapacity HAVING COUNT(att.EmpFK) > 5 ORDER BY FillRate ASC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q28. What percentage of our training catalog has been updated (`LstUpd`) in the last 12 months? 

SQL Query: 

SELECT COUNT(CASE WHEN LstUpd >= NOW() - INTERVAL '12 months' THEN 1 END) * 100.0 / COUNT(Activity_PK) AS PercentUpdated FROM TBL_TMX_Activity_sumtotal; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q29. What is the correlation between the estimated duration of an E-Course and its completion rate? 

SQL Query: 

SELECT act.EstDur::numeric / 60.0 AS DurationMinutes, COUNT(CASE WHEN att.CompletionStatus = 'Completed' THEN 1 END) * 100.0 / COUNT(att.Attempt_PK) AS CompletionRate FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK WHERE al.ActLabel_Name = 'E-Course' AND act.EstDur::numeric > 0 GROUP BY DurationMinutes; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: scatter 

 

Q30. Which 'Micro-video' activities are most frequently viewed, and what is their average elapsed time? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Views, AVG(att.ElapsedSeconds::numeric) AS AvgViewTimeSeconds FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK WHERE al.ActLabel_Name = 'Micro-video' GROUP BY act.Activityme ORDER BY Views DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q31. What is the overall success rate (Passed vs. Failed) for all activities that have 'Quiz' in their name? 

SQL Query: 

SELECT Success, COUNT(Attempt_PK) AS Count FROM TBL_TMX_Attempt_sumtotal WHERE ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Quiz%') AND Success IN ('Passed', 'Failed') GROUP BY Success; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q32. How many unique users have completed at least one 'Leadership Skills' course in the past year? 

SQL Query: 

SELECT COUNT(DISTINCT att.EmpFK) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE act.Activityme LIKE '%Leadership Skills%' AND att.CompletionStatus = 'Completed' AND att.EndDt >= NOW() - INTERVAL '1 year'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q33. What is the trend in the number of certifications set to expire in the next 90 days? 

SQL Query: 

SELECT ExpirationDate::date as ExpirationDay, COUNT(EmpFK) as ExpiringCerts FROM TBL_TMX_UserRequiredAct_sumtotal WHERE IsCertification = 1 AND ExpirationDate BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90 days' GROUP BY ExpirationDay ORDER BY ExpirationDay; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q34. Which activities have a high `LaunchCount` but a low completion rate, indicating potential content or technical issues? 

SQL Query: 

SELECT act.Activityme, SUM(att.LaunchCount) AS TotalLaunches, COUNT(CASE WHEN att.CompletionStatus = 'Completed' THEN 1 END) * 100.0 / COUNT(att.Attempt_PK) AS CompletionRate FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK GROUP BY act.Activityme HAVING SUM(att.LaunchCount) > 100 ORDER BY CompletionRate ASC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q35. What is the average number of training activities completed per active user, per month? 

SQL Query: 

SELECT CAST(COUNT(att.Attempt_PK) AS REAL) / COUNT(DISTINCT att.EmpFK) FROM TBL_TMX_Attempt_sumtotal att WHERE att.CompletionStatus = 'Completed' AND att.EndDt >= NOW() - INTERVAL '30 days'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q36. What is the completion rate of training activities for temporary employees (e.g., 'Temp Agency' in `JobName`)? 

SQL Query: 

SELECT (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS CompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN JobUser_sumtotal ju ON ura.EmpFK = ju.PersonFK WHERE ju.JobName LIKE '%Temp Agency%'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q37. Which courses are most frequently taken by employees in senior-level job roles (e.g., 'Supervisor', 'Manager')? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Attempts FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK WHERE ju.JobName LIKE '%Supervisor%' OR ju.JobName LIKE '%Manager%' GROUP BY act.Activityme ORDER BY Attempts DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q38. What is the average user satisfaction score for our top 20 most popular courses (if a score is used as a satisfaction metric)? 

SQL Query: 

SELECT act.Activityme, AVG(att.Score::numeric) AS AvgSatisfactionScore FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE act.Activityme LIKE '%Survey%' GROUP BY act.Activityme ORDER BY COUNT(att.Attempt_PK) DESC LIMIT 20; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q39. How many courses are currently assigned that are marked as inactive in the activity table? 

SQL Query: 

SELECT COUNT(ura.ActivityFK) FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.IsSatisfied = 0 AND act.Active = 0; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q40. What is the trend of `Ad Hoc Course` completions versus formally assigned courses? 

SQL Query: 

SELECT TO_CHAR(att.EndDt, 'YYYY-MM') AS Month, COUNT(CASE WHEN al.ActLabel_Name = 'Ad Hoc Course' THEN 1 END) AS AdHocCompletions, COUNT(CASE WHEN al.ActLabel_Name <> 'Ad Hoc Course' THEN 1 END) AS FormalCompletions FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK WHERE att.CompletionStatus = 'Completed' AND att.EndDt >= NOW() - INTERVAL '1 year' GROUP BY Month ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q41. What is the overall compliance percentage for mandatory training that was due last quarter, broken down by organization? 

SQL Query: 

SELECT o.VEme AS Organization, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS ComplianceRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN PersonOrganization_sumtotal po ON ura.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE ura.DueDate BETWEEN DATE_TRUNC('quarter', NOW()) - INTERVAL '3 months' AND DATE_TRUNC('quarter', NOW()) - INTERVAL '1 day' GROUP BY Organization ORDER BY ComplianceRate DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q42. Which employees are currently overdue on their 'Supervisor Health & Safety Awareness' training? 

SQL Query: 

SELECT p.FullName, pc.Email1, ura.DueDate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK JOIN PersonCommunication_sumtotal pc ON p.PersonPK = pc.PersonFK WHERE act.Activityme LIKE '%Supervisor Health & Safety Awareness%' AND ura.IsSatisfied = 0 AND ura.DueDate < CURRENT_DATE; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q43. Generate a list of all employees whose 'First Aid/CPR/AED Certification' is set to expire in the next 60 days. 

SQL Query: 

SELECT p.FullName, pc.Email1, ura.ExpirationDate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN PersonCommunication_sumtotal pc ON p.PersonPK = pc.PersonFK WHERE ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%First Aid/CPR/AED%') AND ura.ExpirationDate BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '60 days'; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q44. What percentage of employees in the 'Production Team Member' job role have not completed their assigned safety training? 

SQL Query: 

SELECT (COUNT(CASE WHEN ura.IsSatisfied = 0 THEN 1 END) * 100.0) / COUNT(ura.EmpFK) AS NonComplianceRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN JobUser_sumtotal ju ON ura.EmpFK = ju.PersonFK WHERE ju.JobName = 'Production Team Member' AND ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Safety%'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q45. Which managers have the highest number of direct reports with overdue mandatory training? 

SQL Query: 

SELECT mgr.FullName AS ManagerName, COUNT(DISTINCT pr.PersonFK) AS OverdueReports FROM PersonRelation_sumtotal pr JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON pr.PersonFK = ura.EmpFK JOIN Person_sumtotal mgr ON pr.Manager1FK = mgr.PersonPK WHERE ura.IsSatisfied = 0 AND ura.DueDate < CURRENT_DATE GROUP BY ManagerName ORDER BY OverdueReports DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q46. What is the average delay (in days) for completing overdue compliance training? 

SQL Query: 

SELECT AVG(CURRENT_DATE - DueDate::date) AS AvgOverdueDays FROM TBL_TMX_UserRequiredAct_sumtotal WHERE IsSatisfied = 0 AND DueDate < CURRENT_DATE; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q47. Identify all users who have failed a critical compliance assessment (e.g., 'Live Fire Extinguisher') more than twice. 

SQL Query: 

SELECT p.FullName, act.Activityme, COUNT(att.Attempt_PK) AS Failures FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.Success = 'Failed' AND act.Activityme LIKE '%Live Fire Extinguisher%' GROUP BY p.FullName, act.Activityme HAVING COUNT(att.Attempt_PK) > 2; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q48. What is the completion status of the 'Charter & Guidelines for Business Ethics' policy for all active employees? 

SQL Query: 

SELECT CASE WHEN ura.IsSatisfied = 1 THEN 'Completed' ELSE 'Not Completed' END AS Status, COUNT(DISTINCT ura.EmpFK) AS EmployeeCount FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK WHERE ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Charter & Guidelines for Business Ethics%') AND p.Active = 1 GROUP BY Status; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q49. Which organization (department) has the highest rate of overdue compliance training? 

SQL Query: 

SELECT o.VEme, COUNT(CASE WHEN ura.IsSatisfied = 0 AND ura.DueDate < CURRENT_DATE THEN 1 END) * 100.0 / COUNT(ura.EmpFK) AS OverdueRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN PersonOrganization_sumtotal po ON ura.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK GROUP BY o.VEme ORDER BY OverdueRate DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q50. List all required training that is past its due date but still has an 'Assigned' status. 

SQL Query: 

SELECT p.FullName, act.Activityme, ura.DueDate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.ReqStatus = 'Assigned' AND ura.DueDate < CURRENT_DATE; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q51. What is the compliance rate for 'Indoor Hoisting and Rigging' training for all employees located in Texas? 

SQL Query: 

SELECT (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS ComplianceRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN PersonCommunication_sumtotal pc ON ura.EmpFK = pc.PersonFK WHERE pc.StateName = 'Texas' AND ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Indoor Hoisting and Rigging%'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q52. How many employees completed the 'Pulmonary Function Test (Annual Physical)' requirement ahead of their due date this year? 

SQL Query: 

SELECT COUNT(DISTINCT att.EmpFK) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON att.EmpFK = ura.EmpFK AND att.ActivityFK = ura.ActivityFK WHERE att.CompletionStatus = 'Completed' AND att.EndDt < ura.DueDate AND att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Pulmonary Function Test%'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q53. What is the trend of our overall compliance completion rate over the last four quarters? 

SQL Query: 

SELECT TO_CHAR(DueDate, 'YYYY-"Q"Q') AS Quarter, (SUM(CASE WHEN IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(EmpFK)) * 100 AS ComplianceRate FROM TBL_TMX_UserRequiredAct_sumtotal WHERE DueDate >= DATE_TRUNC('year', NOW()) - INTERVAL '1 year' GROUP BY Quarter ORDER BY Quarter; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q54. Identify any active employees who do not have the 'Intro to - Orientation' training marked as completed. 

SQL Query: 

SELECT p.FullName FROM Person_sumtotal p WHERE p.Active = 1 AND p.PersonPK NOT IN (SELECT EmpFK FROM TBL_TMX_UserRequiredAct_sumtotal WHERE IsSatisfied = 1 AND ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Intro to % Orientation%')); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q55. What is the first-attempt pass rate for the 'Live Fire Extinguisher Instructor Certification' assessment? 

SQL Query: 

WITH FirstAttempts AS (SELECT EmpFK, MIN(StartDt) as FirstStart FROM TBL_TMX_Attempt_sumtotal WHERE ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Live Fire Extinguisher%') GROUP BY EmpFK) SELECT COUNT(CASE WHEN att.Success = 'Passed' THEN 1 END) * 100.0 / COUNT(att.Attempt_PK) FROM TBL_TMX_Attempt_sumtotal att JOIN FirstAttempts fa ON att.EmpFK = fa.EmpFK AND att.StartDt = fa.FirstStart; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q56. Which required training has the highest failure rate on the first attempt across the company? 

SQL Query: 

WITH FirstAttempts AS (SELECT EmpFK, ActivityFK, MIN(StartDt) as FirstStart FROM TBL_TMX_Attempt_sumtotal GROUP BY EmpFK, ActivityFK), FailedFirsts AS (SELECT att.ActivityFK FROM TBL_TMX_Attempt_sumtotal att JOIN FirstAttempts fa ON att.EmpFK = fa.EmpFK AND att.StartDt = fa.FirstStart WHERE att.Success = 'Failed') SELECT act.Activityme, COUNT(ff.ActivityFK) AS FailureCount FROM FailedFirsts ff JOIN TBL_TMX_Activity_sumtotal act ON ff.ActivityFK = act.Activity_PK GROUP BY act.Activityme ORDER BY FailureCount DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q57. Generate a report of all employees with required training due in the next 30 days, including their manager's email for notification. 

SQL Query: 

SELECT p.FullName, act.Activityme, ura.DueDate, mgr_comm.Email1 AS ManagerEmail FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK JOIN PersonRelation_sumtotal pr ON p.PersonPK = pr.PersonFK LEFT JOIN PersonCommunication_sumtotal mgr_comm ON pr.Manager1FK = mgr_comm.PersonFK WHERE ura.IsSatisfied = 0 AND ura.DueDate BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q58. What is the overall satisfaction status (`IsSatisfied`) for all activities marked as a certification (`IsCertification` = 1)? 

SQL Query: 

SELECT CASE WHEN IsSatisfied = 1 THEN 'Certified' ELSE 'Not Certified' END AS Status, COUNT(EmpFK) AS Count FROM TBL_TMX_UserRequiredAct_sumtotal WHERE IsCertification = 1 GROUP BY Status; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q59. Are there any specific job roles with a compliance rate below 85% for their required training? 

SQL Query: 

SELECT ju.JobName, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS ComplianceRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN JobUser_sumtotal ju ON ura.EmpFK = ju.PersonFK WHERE ju.IsPrimary = 1 GROUP BY ju.JobName HAVING (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 < 85 ORDER BY ComplianceRate ASC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q60. How many days, on average, does it take for a new hire (start date in the last 90 days) to complete their initial set of required training? 

SQL Query: 

SELECT AVG(att.EndDt::date - p.StartDate::date) AS AvgDaysToComplete FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE att.CompletionStatus = 'Completed' AND p.StartDate >= NOW() - INTERVAL '90 days' AND att.ActivityFK IN (SELECT ActivityFK FROM TBL_TMX_UserRequiredAct_sumtotal WHERE EmpFK = p.PersonPK); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q61. List all 'Requirement' type activities and their overall completion percentage. 

SQL Query: 

SELECT act.Activityme, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS CompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK WHERE al.ActLabel_Name = 'Requirement' GROUP BY act.Activityme ORDER BY CompletionRate DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q62. What is the current completion status of the 'Employee Satisfaction Survey' across the company? 

SQL Query: 

SELECT att.CompletionStatus, COUNT(DISTINCT att.EmpFK) AS EmployeeCount FROM TBL_TMX_Attempt_sumtotal att WHERE att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Employee Satisfaction Survey%') GROUP BY att.CompletionStatus; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: donut 

 

Q63. Which users have had their compliance training waived (`WaiveInd` = 1), and for which specific activities? 

SQL Query: 

SELECT p.FullName, act.Activityme FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.WaiveInd = 1; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q64. Show a list of all compliance activities and the date they were last updated to ensure they are current with regulations. 

SQL Query: 

SELECT Activityme, LstUpd FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Compliance%' OR Activityme LIKE '%Safety%' ORDER BY LstUpd ASC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q65. What is the trend of recertification completions versus expirations for the top 5 most critical certifications? 

SQL Query: 

SELECT TO_CHAR(ura.ExpirationDate, 'YYYY-MM') AS Month, act.Activityme, COUNT(ura.EmpFK) AS Expiring, COUNT(att.Attempt_PK) AS Recompleted FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK LEFT JOIN TBL_TMX_Attempt_sumtotal att ON ura.EmpFK = att.EmpFK AND ura.ActivityFK = att.ActivityFK AND att.EndDt > ura.LstUpd WHERE ura.IsCertification = 1 AND ura.ExpirationDate IS NOT NULL GROUP BY Month, act.Activityme ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q66. What is the overall training completion percentage for my department for the current year? 

SQL Query: 

SELECT (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS CompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN PersonOrganization_sumtotal po ON ura.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]' AND ura.PlanDate >= DATE_TRUNC('year', NOW()); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q67. Who are the top 5 learners in my department based on the number of completed courses in the last 6 months? 

SQL Query: 

SELECT p.FullName, COUNT(att.Attempt_PK) AS CoursesCompleted FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE att.CompletionStatus = 'Completed' AND att.EndDt >= NOW() - INTERVAL '6 months' AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY p.FullName ORDER BY CoursesCompleted DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q68. Which of my team members have overdue required training, and how many days are they overdue? 

SQL Query: 

SELECT p.FullName, act.Activityme, (CURRENT_DATE - ura.DueDate::date) AS DaysOverdue FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.IsSatisfied = 0 AND ura.DueDate < CURRENT_DATE AND ura.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') ORDER BY DaysOverdue DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q69. What is the average assessment score of my team on the 'Cost Management' course compared to the company-wide average? 

SQL Query: 

SELECT 'My Team' AS Category, AVG(att.Score::numeric) AS AverageScore FROM TBL_TMX_Attempt_sumtotal att WHERE att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Cost Management%') AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') UNION ALL SELECT 'Company' AS Category, AVG(Score::numeric) FROM TBL_TMX_Attempt_sumtotal WHERE ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Cost Management%'); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q70. What are the most popular elective courses my team members are choosing to take? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Attempts FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND att.ActivityFK NOT IN (SELECT ActivityFK FROM TBL_TMX_UserRequiredAct_sumtotal) GROUP BY act.Activityme ORDER BY Attempts DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q71. How many hours of training has my department consumed in the last quarter? 

SQL Query: 

SELECT SUM(att.ElapsedSeconds::numeric) / 3600.0 AS HoursConsumed FROM TBL_TMX_Attempt_sumtotal att WHERE att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND att.EndDt >= DATE_TRUNC('quarter', NOW()) - INTERVAL '3 months'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q72. What is the current training status for all my new hires from the last 90 days? 

SQL Query: 

SELECT p.FullName, act.Activityme, ura.ReqStatus, ura.DueDate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE p.StartDate >= NOW() - INTERVAL '90 days' AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]'); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q73. Which skills (inferred from course titles like 'Coaching', 'Agile', 'Negotiating') are most prevalent within my team based on their training history? 

SQL Query: 

SELECT CASE WHEN act.Activityme LIKE '%Coaching%' THEN 'Coaching' WHEN act.Activityme LIKE '%Agile%' THEN 'Agile' WHEN act.Activityme LIKE '%Negotiating%' THEN 'Negotiating' ELSE 'Other' END AS Skill, COUNT(att.Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus = 'Completed' AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY Skill ORDER BY Completions DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q74. How does my team's first-attempt pass rate on critical assessments compare to other teams in the same division? 

SQL Query: 

WITH FirstAttempts AS (SELECT EmpFK, ActivityFK, MIN(StartDt) as FirstStart FROM TBL_TMX_Attempt_sumtotal GROUP BY EmpFK, ActivityFK) SELECT o.VEme, COUNT(CASE WHEN att.Success = 'Passed' THEN 1 END) * 100.0 / COUNT(att.Attempt_PK) AS PassRate FROM TBL_TMX_Attempt_sumtotal att JOIN FirstAttempts fa ON att.EmpFK = fa.EmpFK AND att.StartDt = fa.FirstStart JOIN PersonOrganization_sumtotal po ON att.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.ParentOrganizationFK = (SELECT ParentOrganizationFK FROM Organization_sumtotal WHERE VEme = '[Your Department Name]') GROUP BY o.VEme; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q75. What is the total training cost incurred by my department in the current fiscal year? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND att.StartDt >= DATE_TRUNC('year', NOW()); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q76. Are there any employees on my team who have not completed any training in the last 12 months? 

SQL Query: 

SELECT p.FullName FROM Person_sumtotal p WHERE p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND p.PersonPK NOT IN (SELECT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE EndDt >= NOW() - INTERVAL '12 months'); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q77. What is the distribution of training completions across the different job roles within my department? 

SQL Query: 

SELECT ju.JobName, COUNT(att.Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal att JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK WHERE att.CompletionStatus = 'Completed' AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY ju.JobName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: donut 

 

Q78. Which upcoming ILT classes have members of my team registered for? 

SQL Query: 

SELECT p.FullName, act.Activityme, act.StartDt FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus IS NULL AND act.StartDt > CURRENT_DATE AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]'); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q79. What is the average time my team members take to complete their assigned mandatory training versus the company average? 

SQL Query: 

SELECT 'My Team' AS Category, AVG(att.EndDt::date - ura.PlanDate::date) AS AvgDays FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON att.EmpFK = ura.EmpFK AND att.ActivityFK = ura.ActivityFK WHERE att.CompletionStatus = 'Completed' AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') UNION ALL SELECT 'Company' AS Category, AVG(att.EndDt::date - ura.PlanDate::date) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON att.EmpFK = ura.EmpFK AND att.ActivityFK = ura.ActivityFK WHERE att.CompletionStatus = 'Completed'; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q80. Identify potential skill gaps by showing which team members have not completed the core set of courses recommended for their job role. 

SQL Query: 

SELECT p.FullName, ju.JobName, 'Core Skill Course Name' AS MissingCourse FROM Person_sumtotal p JOIN JobUser_sumtotal ju ON p.PersonPK = ju.PersonFK WHERE ju.IsPrimary = 1 AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND p.PersonPK NOT IN (SELECT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed' AND ActivityFK = [Core_Activity_FK]); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q81. What percentage of my team has completed the 'Promoting Respect in the Workplace' course? 

SQL Query: 

SELECT COUNT(DISTINCT CASE WHEN att.CompletionStatus = 'Completed' THEN att.EmpFK END) * 100.0 / COUNT(DISTINCT p.PersonPK) AS CompletionPercentage FROM Person_sumtotal p LEFT JOIN TBL_TMX_Attempt_sumtotal att ON p.PersonPK = att.EmpFK AND att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Promoting Respect%') WHERE p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q82. Show the learning progress of my team on the 'TRAINING WITHIN INDUSTRY' curriculum. 

SQL Query: 

SELECT p.FullName, COUNT(CASE WHEN ura.IsSatisfied = 1 THEN 1 END) AS CompletedModules, COUNT(ura.ActivityFK) AS TotalModules FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK WHERE ura.ActivityFK IN (SELECT a.Activity_PK FROM TBL_TMX_Activity_sumtotal a JOIN TBL_TMX_Activity_sumtotal c ON a.PrntActFK = c.Activity_PK WHERE c.Activityme LIKE '%TRAINING WITHIN INDUSTRY%') AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY p.FullName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q83. What is the trend of training activity for my department over the past 12 months? 

SQL Query: 

SELECT TO_CHAR(att.StartDt, 'YYYY-MM') AS Month, COUNT(att.Attempt_PK) AS ActivitiesStarted FROM TBL_TMX_Attempt_sumtotal att WHERE att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND att.StartDt >= NOW() - INTERVAL '12 months' GROUP BY Month ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q84. Which members of my team are certified as 'Mentors' based on their training? 

SQL Query: 

SELECT p.FullName FROM Person_sumtotal p JOIN TBL_TMX_Attempt_sumtotal att ON p.PersonPK = att.EmpFK JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus = 'Completed' AND act.Activityme LIKE '%Mentor Certification%' AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]'); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q85. How do my direct reports compare in terms of courses completed and hours spent on training? 

SQL Query: 

SELECT p.FullName, COUNT(att.Attempt_PK) AS CoursesCompleted, SUM(att.ElapsedSeconds::numeric)/3600.0 AS HoursSpent FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE att.CompletionStatus = 'Completed' AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY p.FullName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q86. What is the pass/fail ratio for all assessments taken by my team in the last quarter? 

SQL Query: 

SELECT att.Success, COUNT(att.Attempt_PK) AS Count FROM TBL_TMX_Attempt_sumtotal att WHERE att.Success IN ('Passed', 'Failed') AND att.EndDt >= DATE_TRUNC('quarter', NOW()) - INTERVAL '3 months' AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY att.Success; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q87. Which of my team members have certifications expiring in the next six months? 

SQL Query: 

SELECT p.FullName, act.Activityme, ura.ExpirationDate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.IsCertification = 1 AND ura.ExpirationDate BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '6 months' AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]'); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q88. What is the most common day of the week for my team to complete training activities? 

SQL Query: 

SELECT TO_CHAR(EndDt, 'Day') AS DayOfWeek, COUNT(Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed' AND EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY DayOfWeek ORDER BY Completions DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q89. How many of my team members are assigned to the 'Team Leader' job role versus 'Team Member'? 

SQL Query: 

SELECT ju.JobName, COUNT(p.PersonPK) AS EmployeeCount FROM Person_sumtotal p JOIN JobUser_sumtotal ju ON p.PersonPK = ju.PersonFK WHERE ju.IsPrimary = 1 AND p.PersonPK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') AND ju.JobName IN ('Team Leader', 'Team Member') GROUP BY ju.JobName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q90. What is the breakdown of training completions by activity type (E-Course vs. ILT vs. Micro-video) for my department? 

SQL Query: 

SELECT al.ActLabel_Name, COUNT(att.Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK WHERE att.CompletionStatus = 'Completed' AND att.EmpFK IN (SELECT PersonFK FROM PersonOrganization_sumtotal po JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme = '[Your Department Name]') GROUP BY al.ActLabel_Name; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: donut 

 

Q91. What is the completion rate of the standard onboarding curriculum for all employees who started in the last quarter? 

SQL Query: 

SELECT (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS OnboardingCompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK WHERE p.StartDate >= DATE_TRUNC('quarter', NOW()) - INTERVAL '3 months' AND ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Onboarding%'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q92. What is the average time-to-completion for the 'Intro to - Orientation' course for new hires? 

SQL Query: 

SELECT AVG(att.EndDt::date - p.StartDate::date) AS AvgDaysToComplete FROM TBL_TMX_Attempt_sumtotal att JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE att.CompletionStatus = 'Completed' AND p.StartDate >= NOW() - INTERVAL '1 year' AND att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Intro to % Orientation%'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q93. Is there a correlation between an employee's job role and the number of training hours completed annually? 

SQL Query: 

SELECT ju.JobName, AVG(TotalHours) AS AvgAnnualHours FROM (SELECT att.EmpFK, SUM(att.ElapsedSeconds::numeric)/3600.0 AS TotalHours FROM TBL_TMX_Attempt_sumtotal att WHERE att.EndDt >= NOW() - INTERVAL '1 year' GROUP BY att.EmpFK) AS UserHours JOIN JobUser_sumtotal ju ON UserHours.EmpFK = ju.PersonFK WHERE ju.IsPrimary = 1 GROUP BY ju.JobName ORDER BY AvgAnnualHours DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q94. What are the top 5 training courses completed by employees in the 'OPERARIO DE PRODUCCION' job role? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK WHERE ju.JobName = 'OPERARIO DE PRODUCCION' AND att.CompletionStatus = 'Completed' GROUP BY act.Activityme ORDER BY Completions DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q95. What percentage of employees have completed the 'Diversity in the Workplace' training, broken down by country? 

SQL Query: 

SELECT pc.Country, COUNT(DISTINCT CASE WHEN att.CompletionStatus = 'Completed' THEN pc.PersonFK END) * 100.0 / COUNT(DISTINCT pc.PersonFK) AS CompletionPercentage FROM PersonCommunication_sumtotal pc LEFT JOIN TBL_TMX_Attempt_sumtotal att ON pc.PersonFK = att.EmpFK AND att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Diversity%') GROUP BY pc.Country; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q96. How many active employees have a `StatusCode` other than 'Active' (e.g., on leave)? 

SQL Query: 

SELECT StatusCode, COUNT(PersonPK) FROM Person_sumtotal WHERE Active = 1 AND StatusCode <> 1 GROUP BY StatusCode; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q97. What does the training completion profile look like for our top performers (modeled by identifying top learners)? 

SQL Query: 

WITH TopLearners AS (SELECT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed' GROUP BY EmpFK ORDER BY COUNT(Attempt_PK) DESC LIMIT 50) SELECT act.Activityme, COUNT(att.Attempt_PK) AS Completions FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.EmpFK IN (SELECT EmpFK FROM TopLearners) GROUP BY act.Activityme ORDER BY Completions DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q98. What is the average tenure of employees who have completed advanced leadership training programs? 

SQL Query: 

SELECT AVG( (CURRENT_DATE - p.StartDate::date)/365.25 ) AS AvgTenureYears FROM Person_sumtotal p WHERE p.PersonPK IN (SELECT DISTINCT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed' AND ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Leadership%')); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q99. Which job roles have the highest number of required training assignments? 

SQL Query: 

SELECT ju.JobName, COUNT(ura.ActivityFK) AS RequiredCourses FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN JobUser_sumtotal ju ON ura.EmpFK = ju.PersonFK WHERE ju.IsPrimary = 1 GROUP BY ju.JobName ORDER BY RequiredCourses DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q100. What is the distribution of active employees by `CompanyName`? 

SQL Query: 

SELECT CompanyName, COUNT(PersonPK) AS EmployeeCount FROM Person_sumtotal WHERE Active = 1 GROUP BY CompanyName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q101. How many employees who left the company (`EndDate` is not null) in the last year had incomplete mandatory training at the time of their departure? 

SQL Query: 

SELECT COUNT(DISTINCT p.PersonPK) FROM Person_sumtotal p JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON p.PersonPK = ura.EmpFK WHERE p.EndDate >= NOW() - INTERVAL '1 year' AND ura.IsSatisfied = 0; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q102. What are the most common training activities for employees with a `JoiningDate` in the last 30 days? 

SQL Query: 

SELECT act.Activityme, COUNT(att.Attempt_PK) AS Attempts FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE p.StartDate >= NOW() - INTERVAL '30 days' GROUP BY act.Activityme ORDER BY Attempts DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q103. What is the gender distribution (`GenderCode`) of enrollments in our leadership development programs? 

SQL Query: 

SELECT p.GenderCode, COUNT(DISTINCT p.PersonPK) AS EnrollmentCount FROM Person_sumtotal p JOIN TBL_TMX_Attempt_sumtotal att ON p.PersonPK = att.EmpFK WHERE att.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Leadership%') GROUP BY p.GenderCode; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q104. How many employees are currently in a 'Temp Agency' job role, and what is their average tenure? 

SQL Query: 

SELECT COUNT(PersonPK) AS TempCount, AVG( (CURRENT_DATE - JoiningDate::date)/30.44 ) AS AvgTenureMonths FROM JobUser_sumtotal WHERE JobName LIKE '%Temp Agency%'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q105. What is the average number of days between an employee's `StartDate` and their first training `Attempt`? 

SQL Query: 

WITH FirstAttempt AS (SELECT EmpFK, MIN(StartDt) AS FirstAttemptDate FROM TBL_TMX_Attempt_sumtotal GROUP BY EmpFK) SELECT AVG(fa.FirstAttemptDate::date - p.StartDate::date) AS AvgDaysToFirstTraining FROM FirstAttempt fa JOIN Person_sumtotal p ON fa.EmpFK = p.PersonPK; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q106. Which departments have the highest concentration of employees with the 'Team Leader' job title? 

SQL Query: 

SELECT o.VEme, COUNT(p.PersonPK) AS TeamLeaderCount FROM Person_sumtotal p JOIN JobUser_sumtotal ju ON p.PersonPK = ju.PersonFK JOIN PersonOrganization_sumtotal po ON p.PersonPK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE ju.JobName = 'Team Leader' GROUP BY o.VEme ORDER BY TeamLeaderCount DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q107. What is the completion rate for training related to 'Business Ethics' across different employee levels (inferred from job titles)? 

SQL Query: 

SELECT CASE WHEN ju.JobName LIKE '%Supervisor%' THEN 'Supervisor' WHEN ju.JobName LIKE '%Manager%' THEN 'Manager' ELSE 'Individual Contributor' END AS Level, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS CompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN JobUser_sumtotal ju ON ura.EmpFK = ju.PersonFK WHERE ura.ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Business Ethics%') GROUP BY Level; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q108. How many employees have provided their LinkedIn URL in their communication profile? 

SQL Query: 

SELECT COUNT(PersonFK) FROM PersonCommunication_sumtotal WHERE LinkedInURL IS NOT NULL AND LinkedInURL <> ''; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q109. What is the breakdown of our workforce by state (`StateName`)? 

SQL Query: 

SELECT StateName, COUNT(PersonFK) AS EmployeeCount FROM PersonCommunication_sumtotal WHERE StateName IS NOT NULL AND StateName <> '' GROUP BY StateName ORDER BY EmployeeCount DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q110. Are there any employees who have been with the company for over a year but have not completed any training? 

SQL Query: 

SELECT COUNT(p.PersonPK) FROM Person_sumtotal p WHERE p.StartDate < NOW() - INTERVAL '1 year' AND p.Active = 1 AND p.PersonPK NOT IN (SELECT DISTINCT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q111. What is the total number of active employees versus inactive employees in the system? 

SQL Query: 

SELECT Active, COUNT(PersonPK) AS Count FROM Person_sumtotal GROUP BY Active; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q112. What is the average number of job role changes (`JobUser` entries per person) for employees who have completed management training? 

SQL Query: 

WITH RoleChanges AS (SELECT PersonFK, COUNT(JobTemplateFK) AS Roles FROM JobUser_sumtotal GROUP BY PersonFK) SELECT AVG(rc.Roles) FROM RoleChanges rc WHERE rc.PersonFK IN (SELECT DISTINCT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'Completed' AND ActivityFK IN (SELECT Activity_PK FROM TBL_TMX_Activity_sumtotal WHERE Activityme LIKE '%Management%')); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q113. Which employees are assigned to the 'Intern D2' job and what is their training completion status? 

SQL Query: 

SELECT p.FullName, (SUM(CASE WHEN ura.IsSatisfied = 1 THEN 1.0 ELSE 0.0 END) / COUNT(ura.EmpFK)) * 100 AS CompletionRate FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN Person_sumtotal p ON ura.EmpFK = p.PersonPK WHERE p.PersonPK IN (SELECT PersonFK FROM JobUser_sumtotal WHERE JobName = 'Intern D2') GROUP BY p.FullName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q114. What is the distribution of our employees by timezone? 

SQL Query: 

SELECT TimeZoneFK, COUNT(PersonPK) AS EmployeeCount FROM Person_sumtotal GROUP BY TimeZoneFK ORDER BY EmployeeCount DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q115. How many employees have a birthday in the current month (for recognition and engagement purposes)? 

SQL Query: 

SELECT COUNT(PersonPK) FROM Person_sumtotal WHERE EXTRACT(MONTH FROM BirthDate) = EXTRACT(MONTH FROM NOW()); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q116. How many active users have not logged an attempt on any course in the last 12 months? 

SQL Query: 

SELECT COUNT(p.PersonPK) FROM Person_sumtotal p WHERE p.Active = 1 AND p.PersonPK NOT IN (SELECT DISTINCT EmpFK FROM TBL_TMX_Attempt_sumtotal WHERE StartDt >= NOW() - INTERVAL '12 months'); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q117. Are there any duplicate `PersonNumber` or `GovtId` entries in the Person table that need cleaning? 

SQL Query: 

SELECT PersonNumber, COUNT(PersonPK) FROM Person_sumtotal GROUP BY PersonNumber HAVING COUNT(PersonPK) > 1; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q118. List all activities that have a `CostBase` greater than zero but have never been attempted. 

SQL Query: 

SELECT Activityme, CostBase FROM TBL_TMX_Activity_sumtotal WHERE CostBase::numeric > 0 AND Activity_PK NOT IN (SELECT DISTINCT ActivityFK FROM TBL_TMX_Attempt_sumtotal); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q119. How many users have a generic email domain (e.g., gmail.com, yahoo.com) versus a corporate email? 

SQL Query: 

SELECT CASE WHEN Email1 LIKE '%@gmail.com' OR Email1 LIKE '%@yahoo.com' THEN 'Generic' ELSE 'Corporate' END AS EmailType, COUNT(PersonFK) AS UserCount FROM PersonCommunication_sumtotal GROUP BY EmailType; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q120. What is the total number of attempt records in the system, and how has this number grown month-over-month? 

SQL Query: 

SELECT TO_CHAR(StartDt, 'YYYY-MM') AS Month, COUNT(Attempt_PK) AS Attempts FROM TBL_TMX_Attempt_sumtotal GROUP BY Month ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q121. Are there any activities assigned as required that are currently marked as inactive (`Active`=0 in `TBL_TMX_Activity`)? 

SQL Query: 

SELECT COUNT(DISTINCT ura.ActivityFK) FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.IsSatisfied = 0 AND act.Active = 0; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q122. How many users have a `SynchFaultFlg` set to a value other than -1 in the `PersonOrganization` table, indicating a sync issue? 

SQL Query: 

SELECT COUNT(PersonFK) FROM PersonOrganization_sumtotal WHERE SynchFaultFlg <> -1; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q123. What is the volume of training records created by `tmbatchimportuser` versus other system users or admins? 

SQL Query: 

SELECT CreatedBy, COUNT(PersonPK) AS RecordsCreated FROM Person_sumtotal GROUP BY CreatedBy ORDER BY RecordsCreated DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q124. List all users who are missing a primary job assignment (`IsPrimary`=0 for all their jobs). 

SQL Query: 

SELECT p.FullName FROM Person_sumtotal p WHERE p.PersonPK NOT IN (SELECT PersonFK FROM JobUser_sumtotal WHERE IsPrimary = 1); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q125. What is the data integrity of the location fields (`City`, `StateName`) in `PersonCommunication` (i.e., how many are null or contain inconsistent values)? 

SQL Query: 

SELECT 'Null City' AS Metric, COUNT(*) FROM PersonCommunication_sumtotal WHERE City IS NULL OR City = '' UNION ALL SELECT 'Null State' AS Metric, COUNT(*) FROM PersonCommunication_sumtotal WHERE StateName IS NULL OR StateName = ''; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q126. How many curricula (`ActLabel_Name` = 'Curriculum') have no child activities linked to them via `PrntActFK`? 

SQL Query: 

SELECT COUNT(c.Activity_PK) FROM TBL_TMX_Activity_sumtotal c JOIN Actlabel_sumtotal al ON c.ActivityLabelFK = al.ActLabel_PK WHERE al.ActLabel_Name = 'Curriculum' AND c.Activity_PK NOT IN (SELECT DISTINCT PrntActFK FROM TBL_TMX_Activity_sumtotal WHERE PrntActFK IS NOT NULL); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q127. What is the average number of attempts per user across the entire system? 

SQL Query: 

SELECT CAST(COUNT(Attempt_PK) AS REAL) / COUNT(DISTINCT EmpFK) AS AvgAttemptsPerUser FROM TBL_TMX_Attempt_sumtotal; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q128. Are there any users marked as inactive (`Active`=0 in `Person`) who still have active required training assignments? 

SQL Query: 

SELECT COUNT(DISTINCT p.PersonPK) FROM Person_sumtotal p JOIN TBL_TMX_UserRequiredAct_sumtotal ura ON p.PersonPK = ura.EmpFK WHERE p.Active = 0 AND ura.IsSatisfied = 0; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q129. What is the total count of activities broken down by their label (E-Course, Document, etc.)? 

SQL Query: 

SELECT al.ActLabel_Name, COUNT(act.Activity_PK) AS ActivityCount FROM TBL_TMX_Activity_sumtotal act JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK GROUP BY al.ActLabel_Name ORDER BY ActivityCount DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q130. Identify any attempt records where the `EndDt` is earlier than the `StartDt`, indicating a data quality issue. 

SQL Query: 

SELECT Attempt_PK, EmpFK, ActivityFK, StartDt, EndDt FROM TBL_TMX_Attempt_sumtotal WHERE EndDt < StartDt; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q131. How many organizations exist in the system that have no people assigned to them? 

SQL Query: 

SELECT COUNT(OrganizationPK) FROM Organization_sumtotal WHERE OrganizationPK NOT IN (SELECT DISTINCT OrganizationFK FROM PersonOrganization_sumtotal); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q132. What percentage of users have a `FriendlyName` populated in their profile? 

SQL Query: 

SELECT COUNT(CASE WHEN FriendlyName IS NOT NULL AND FriendlyName <> '' THEN 1 END) * 100.0 / COUNT(PersonPK) FROM Person_sumtotal; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: gauge 

 

Q133. List all activities where `MaxCapacity` is set but there are no recorded attempts. 

SQL Query: 

SELECT Activityme, MaxCapacity FROM TBL_TMX_Activity_sumtotal WHERE MaxCapacity::numeric > 0 AND Activity_PK NOT IN (SELECT DISTINCT ActivityFK FROM TBL_TMX_Attempt_sumtotal); 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q134. How many attempt records are stuck 'In Progress' with a `StartDt` more than 90 days ago? 

SQL Query: 

SELECT COUNT(Attempt_PK) FROM TBL_TMX_Attempt_sumtotal WHERE CompletionStatus = 'In Progress' AND StartDt < NOW() - INTERVAL '90 days'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q135. What are the top 10 most recently updated activities based on the `LstUpd` date in `TBL_TMX_Activity`? 

SQL Query: 

SELECT Activityme, LstUpd FROM TBL_TMX_Activity_sumtotal ORDER BY LstUpd DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: table 

 

Q136. How many users are missing a corresponding entry in the `PersonCommunication` table? 

SQL Query: 

SELECT COUNT(p.PersonPK) FROM Person_sumtotal p WHERE p.PersonPK NOT IN (SELECT PersonFK FROM PersonCommunication_sumtotal); 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q137. What is the distribution of `ModifierFK` values in the `TBL_TMX_Attempt` table to see who is modifying records? 

SQL Query: 

SELECT ModifierFK, COUNT(Attempt_PK) AS Modifications FROM TBL_TMX_Attempt_sumtotal WHERE ModifierFK IS NOT NULL GROUP BY ModifierFK ORDER BY Modifications DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q138. Are there any users with an `EndDate` in the past who are still marked as `Active`? 

SQL Query: 

SELECT COUNT(PersonPK) FROM Person_sumtotal WHERE EndDate < CURRENT_DATE AND Active = 1; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q139. How many activities have a `LaunchCourseVersion` populated, indicating they are versioned content? 

SQL Query: 

SELECT COUNT(Activity_PK) FROM TBL_TMX_Activity_sumtotal WHERE LaunchCourseVersion IS NOT NULL AND LaunchCourseVersion <> ''; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q140. What is the total number of records where the `Deleted` flag is set to 1 across all relevant tables? 

SQL Query: 

SELECT 'Person_sumtotal' AS TableName, COUNT(*) FROM Person_sumtotal WHERE Deleted = 1 UNION ALL SELECT 'PersonOrganization_sumtotal', COUNT(*) FROM PersonOrganization_sumtotal WHERE Deleted = 1 UNION ALL SELECT 'JobUser_sumtotal', COUNT(*) FROM JobUser_sumtotal WHERE Deleted = 1; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q141. What was the total training cost (`CostBase`) for the entire organization in the last fiscal year? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus = 'Completed' AND att.EndDt BETWEEN DATE_TRUNC('year', NOW()) - INTERVAL '1 year' AND DATE_TRUNC('year', NOW()) - INTERVAL '1 day'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q142. What is the breakdown of training costs by department (Organization) for the last 12 months? 

SQL Query: 

SELECT o.VEme, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonOrganization_sumtotal po ON att.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE att.StartDt >= NOW() - INTERVAL '12 months' GROUP BY o.VEme ORDER BY TotalCost DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q143. What is the average training cost per employee (total cost / number of active employees)? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) / (SELECT COUNT(PersonPK) FROM Person_sumtotal WHERE Active = 1) AS AvgCostPerEmployee FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.StartDt >= NOW() - INTERVAL '1 year'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q144. Which 5 courses represent the highest total investment (cost multiplied by the number of completions)? 

SQL Query: 

SELECT act.Activityme, SUM(act.CostBase::numeric) AS TotalInvestment FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus = 'Completed' GROUP BY act.Activityme ORDER BY TotalInvestment DESC LIMIT 5; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q145. How does the training investment per employee differ between the 'Production' and 'Sales' departments? 

SQL Query: 

SELECT o.VEme, SUM(act.CostBase::numeric) / COUNT(DISTINCT att.EmpFK) AS CostPerEmployee FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonOrganization_sumtotal po ON att.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE o.VEme LIKE '%Production%' OR o.VEme LIKE '%Sales%' GROUP BY o.VEme; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q146. What is the total cost associated with training that is currently 'In Progress' and has passed its due date? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.ReqStatus = 'In Progress' AND ura.DueDate < CURRENT_DATE; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q147. Is there a correlation between higher training expenditure in a department and higher average assessment scores? 

SQL Query: 

SELECT o.VEme, SUM(act.CostBase::numeric) AS TotalCost, AVG(att.Score::numeric) AS AvgScore FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonOrganization_sumtotal po ON att.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK WHERE att.Score IS NOT NULL GROUP BY o.VEme; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: scatter 

 

Q148. What is the projected cost for all assigned but not yet completed required training? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.IsSatisfied = 0; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q149. How do training costs for 'Team Members' compare to those for 'Supervisors'? 

SQL Query: 

SELECT ju.JobName, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK WHERE ju.JobName LIKE '%Team Member%' OR ju.JobName LIKE '%Supervisor%' GROUP BY ju.JobName; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q150. What was the total cost of training for employees who left the company within 6 months of completing that training? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Person_sumtotal p ON att.EmpFK = p.PersonPK WHERE p.EndDate IS NOT NULL AND (p.EndDate::date - att.EndDt::date) < 180; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q151. What is the cost breakdown by activity type (e.g., E-Course vs. ILT)? 

SQL Query: 

SELECT al.ActLabel_Name, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN Actlabel_sumtotal al ON act.ActivityLabelFK = al.ActLabel_PK GROUP BY al.ActLabel_Name ORDER BY TotalCost DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: pie 

 

Q152. What is the total cost of failed or incomplete training attempts, assuming the cost is incurred on launch? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus <> 'Completed'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q153. How does training spend in the US (`Country` = 'USA') compare to Mexico (inferred from cities like 'Matamoros')? 

SQL Query: 

SELECT pc.Country, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonCommunication_sumtotal pc ON att.EmpFK = pc.PersonFK WHERE pc.Country IN ('USA', 'Mexico') GROUP BY pc.Country; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q154. What is the month-over-month trend in training expenditure? 

SQL Query: 

SELECT TO_CHAR(att.StartDt, 'YYYY-MM') AS Month, SUM(act.CostBase::numeric) AS MonthlyCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK GROUP BY Month ORDER BY Month; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: line 

 

Q155. Which job roles incur the highest training costs per person? 

SQL Query: 

SELECT ju.JobName, SUM(act.CostBase::numeric) / COUNT(DISTINCT ju.PersonFK) AS CostPerPerson FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK GROUP BY ju.JobName ORDER BY CostPerPerson DESC LIMIT 10; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q156. What is the total cost associated with certifications that are due to expire in the next year, assuming they will all be renewed? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_UserRequiredAct_sumtotal ura JOIN TBL_TMX_Activity_sumtotal act ON ura.ActivityFK = act.Activity_PK WHERE ura.IsCertification = 1 AND ura.ExpirationDate BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '1 year'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q157. How does the training cost per employee correlate with their tenure in the company? 

SQL Query: 

SELECT CAST( (CURRENT_DATE - p.StartDate::date)/365.25 AS INTEGER) AS TenureYears, SUM(act.CostBase::numeric) / COUNT(DISTINCT p.PersonPK) AS AvgCost FROM Person_sumtotal p JOIN TBL_TMX_Attempt_sumtotal att ON p.PersonPK = att.EmpFK JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE p.Active = 1 GROUP BY TenureYears; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: scatter 

 

Q158. What is the financial impact of overdue training if a penalty is associated with non-compliance? 

SQL Query: 

SELECT COUNT(*) * 100 AS PotentialPenalty FROM TBL_TMX_UserRequiredAct_sumtotal WHERE IsSatisfied = 0 AND DueDate < CURRENT_DATE; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q159. What was the total cost of all 'Leadership' or 'Management' related courses completed in the last year? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.CompletionStatus = 'Completed' AND (act.Activityme LIKE '%Leadership%' OR act.Activityme LIKE '%Management%') AND att.EndDt >= NOW() - INTERVAL '1 year'; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q160. What is the cost of training for temporary staff versus full-time employees? 

SQL Query: 

SELECT CASE WHEN ju.JobName LIKE '%Temp%' THEN 'Temporary' ELSE 'Full-Time' END AS EmployeeType, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN JobUser_sumtotal ju ON att.EmpFK = ju.PersonFK GROUP BY EmployeeType; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q161. Which parent organization (division) has the highest training spend? 

SQL Query: 

SELECT parent.VEme AS ParentOrganization, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonOrganization_sumtotal po ON att.EmpFK = po.PersonFK JOIN Organization_sumtotal o ON po.OrganizationFK = o.OrganizationPK JOIN Organization_sumtotal parent ON o.ParentOrganizationFK = parent.OrganizationPK GROUP BY ParentOrganization ORDER BY TotalCost DESC; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q162. What is the total value of our current training catalog (sum of all `CostBase`)? 

SQL Query: 

SELECT SUM(CostBase::numeric) FROM TBL_TMX_Activity_sumtotal; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q163. How does our training investment compare across different company locations (e.g., 'Hopkinsville' vs. 'San Antonio')? 

SQL Query: 

SELECT pc.City, SUM(act.CostBase::numeric) AS TotalCost FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK JOIN PersonCommunication_sumtotal pc ON att.EmpFK = pc.PersonFK WHERE pc.City IN ('Hopkinsville', 'San Antonio', 'Irapuato') GROUP BY pc.City; 

Visualization Details: 

- Visual Type: chart 

- Chart Type: bar 

 

Q164. What is the estimated cost savings if the top 3 most failed courses had their first-attempt pass rate improved by 10%? 

SQL Query: 

WITH FailedFirsts AS (SELECT ActivityFK, COUNT(*) AS FailCount FROM TBL_TMX_Attempt_sumtotal WHERE Success = 'Failed' AND Attempt_PK IN (SELECT MIN(Attempt_PK) FROM TBL_TMX_Attempt_sumtotal GROUP BY EmpFK, ActivityFK) GROUP BY ActivityFK ORDER BY FailCount DESC LIMIT 3) SELECT SUM(ff.FailCount * 0.10 * act.CostBase::numeric) AS PotentialSavings FROM FailedFirsts ff JOIN TBL_TMX_Activity_sumtotal act ON ff.ActivityFK = act.Activity_PK; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 

Q165. What is the ratio of training cost to the number of hours of training delivered, giving us a 'Cost per Hour' metric? 

SQL Query: 

SELECT SUM(act.CostBase::numeric) / (SUM(att.ElapsedSeconds::numeric) / 3600.0) AS CostPerHour FROM TBL_TMX_Attempt_sumtotal att JOIN TBL_TMX_Activity_sumtotal act ON att.ActivityFK = act.Activity_PK WHERE att.ElapsedSeconds::numeric > 0; 

Visualization Details: 

- Visual Type: kpi 

- Chart Type: metric 

 