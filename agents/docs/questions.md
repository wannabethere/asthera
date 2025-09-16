CSOD Training Dataset Questions
Direct Visualization Questions
Bar Chart
How many trainings are assigned vs completed across different Divisions (Administration, Acme Products, Private Operations)?
Pie Chart
What is the proportion of different Transcript Status (Assigned / Satisfied / Expired / Waived)?
Bar/Column Chart
How many employees have completed the training on time or Late per Division?
Timeline/Line Chart
How has the number of completed trainings changed month by month? (using CompletionDate)
Stacked Bar Chart
Stack training activities by ActivityType and show their Training Statuses (Assigned, Completed, Expired).
Heatmap
Show a heatmap of training completions by Division vs Position.
Top N
Which 5 training activities have the highest number of completions?
Maths / Analytics Questions
Completion Rate
What percentage of assigned trainings have been completed?
Average Completion Time
On average, how many days does it take from AssignmentDate to CompletionDate?
Overdue Analysis
How many trainings were completed after their DueDate (late completions)?
Division Comparison
Which division has the highest completion percentage?
Expired Trainings
How many trainings have expired without being completed?
Cohort Analysis
Employees who were assigned trainings in the same month — how many completed over time?
Manager View
Which managers have the highest or lowest team compliance?
Dashboard Widgets
Employee Training Completion Insights
Analyzes overall training completions across the Divisions, identifying completed vs. not completed employees.Breaks down completion by `Division`, `Position`, or `Manager Name`.Highlights at-risk groups (e.g., late completions, past due users).Supports strategic resource allocation for past due teams.
Questions:
• What is the overall Completion rate across all Assignments?
• Which Division has the lowest compliance rates?
• How does completion rate vary by `Position` (e.g., IT vs. Sales)?
• Which managers oversee the most past due employees?
Training Timeliness Audit
Questions:
• Which `Division` has the highest percentage of late submissions?
• How many active training assignments are overdue by more than 30 days?
• Which `ActivityType` (e.g., 'Compliance Course') is most frequently delayed?
• Do certain managers correlate with higher late submission rates?
Manager Training Oversight Dashboard
Questions:
• Which manager’s team has the highest `past due` rate?
• Do managers with larger teams correlate with lower completions?
• How does `Training Status` vary among teams with different manager tenure?
• Are specific managers prone to assigning overdue activities?
Role-Based Training Effectiveness
Questions:
• Which job roles take the longest to complete assignments on average?
• Do certain roles (`PrimaryJob`) struggle more with certification requirements?
• How does `ActivityType` completion vary between junior vs. senior roles?
• Are compliance gaps concentrated in specific job functions?
Domain/Organization Comparison
Questions:
• Which domain has the highest average completion rate for `ActivityType = "Mandatory"`?
• How does `isCompliant` rate differ between regional offices?
• Do smaller domains outperform larger ones in training adherence?
• Are there domain-specific activity types with high failure rates?
Historical Training Behavior Analysis
Questions:
• Are there monthly/quarterly spikes in assignment volumes (`AssignmentDate`)?
• Has overall compliance (`isCompliant`) improved since last year?
• Do completion rates for new hires differ from veteran employees?
• How has the mix of `ActivityType` (e.g., 'Technical' vs. 'Soft Skills') evolved?

ML Questions:

What are the training completion rate trends by division over the past year?

How do training completion patterns vary seasonally across different divisions?

Which employees have anomalous training completion behaviors that might need attention?

Can we segment employees into groups based on their learning and performance characteristics?
