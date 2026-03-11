# LMS Silver Layer — Schema Definitions
## Tables Required to Derive All Metrics Across the Four Use Cases

**Layer:** Silver (cleaned, conformed, grain-stable)  
**Source Systems:** Cornerstone LMS · Workday HRIS · Finance/ERP · SSO · Vendor Management  
**Medallion Position:** Bronze (raw ingest) → **Silver (these tables)** → Gold (metric aggregations)

---

## Table Index

| # | Table Name | Source System | Primary Use Cases | Row Grain |
|---|---|---|---|---|
| 1 | `lms_learner` | HRIS + LMS | All | One row per employee |
| 2 | `lms_training_activity` | LMS | All | One row per training activity/course |
| 3 | `lms_enrollment` | LMS | 1, 2, 3, 4 | One row per learner × activity assignment |
| 4 | `lms_completion` | LMS | 1, 2, 4 | One row per completed enrollment event |
| 5 | `lms_assessment_attempt` | LMS | 2 | One row per assessment attempt |
| 6 | `lms_session_log` | SSO + LMS | 1, 2 | One row per learner session |
| 7 | `lms_ilt_session` | LMS | 3, 4 | One row per ILT class/session offering |
| 8 | `lms_ilt_registration` | LMS | 3, 4 | One row per learner × ILT session registration |
| 9 | `lms_certification` | LMS | 3 | One row per certification definition |
| 10 | `lms_learner_certification` | LMS | 3 | One row per learner × certification assignment |
| 11 | `lms_ce_credit_log` | LMS | 3 | One row per CE credit earning event |
| 12 | `lms_training_plan` | LMS | 2, 3 | One row per training plan definition |
| 13 | `lms_training_plan_enrollment` | LMS | 2, 3 | One row per learner × training plan assignment |
| 14 | `lms_evaluation_response` | LMS | 2 | One row per evaluation submission |
| 15 | `lms_training_cost` | Finance/ERP | 4 | One row per cost allocation event |
| 16 | `lms_vendor` | Vendor Management | 4 | One row per vendor |
| 17 | `lms_cancellation_log` | LMS | 4 | One row per cancellation event |

---

## Table 1 — `lms_learner`

**Source:** HRIS (Workday) joined with LMS learner profile  
**Grain:** One row per employee  
**Refreshed:** Daily (full refresh from HRIS snapshot)  
**Used by:** All four use cases as the base population denominator and cohort dimension

| Column | Data Type | Description |
|---|---|---|
| `learner_id` | VARCHAR(50) | Surrogate key — stable internal identifier for the learner across LMS and HRIS systems |
| `employee_id` | VARCHAR(50) | HRIS employee number from Workday — foreign key for HRIS joins |
| `full_name` | VARCHAR(200) | Learner display name |
| `email` | VARCHAR(200) | Work email address — used for notification attribution |
| `job_title` | VARCHAR(200) | Current job title as of last HRIS sync |
| `job_family` | VARCHAR(100) | Job family / role family grouping (e.g. Engineering, Sales, Operations) |
| `job_level` | VARCHAR(50) | Grade or level within the job architecture (e.g. IC3, Manager, Director) |
| `department` | VARCHAR(200) | Department name from HRIS org hierarchy |
| `department_id` | VARCHAR(50) | Department identifier — for joining to org hierarchy dimension |
| `cost_center` | VARCHAR(50) | Cost centre code — links learner to financial reporting unit |
| `manager_id` | VARCHAR(50) | Learner's direct manager `employee_id` — used for team-level aggregation |
| `manager_name` | VARCHAR(200) | Manager display name — for manager-level dashboard drill-down |
| `location` | VARCHAR(200) | Office location or "Remote" |
| `region` | VARCHAR(100) | Geographic region (e.g. EMEA, AMER, APAC) |
| `employment_type` | VARCHAR(50) | Full-time, Part-time, Contractor, Intern |
| `employment_status` | VARCHAR(50) | Active, On Leave, Terminated — filters active learner population |
| `hire_date` | DATE | Original hire date — used for tenure-based segmentation |
| `termination_date` | DATE | Termination date — NULL if active; used to exclude leavers from compliance counts |
| `is_licensed_role` | BOOLEAN | TRUE if the role requires active regulatory certification to operate (e.g. clinical, finance, safety) |
| `lms_account_created_at` | TIMESTAMP | Date the learner's LMS account was provisioned |
| `lms_last_active_at` | TIMESTAMP | Timestamp of most recent LMS activity — used for disengagement detection |
| `source_system` | VARCHAR(50) | Source system identifier (e.g. 'workday', 'cornerstone') |
| `synced_at` | TIMESTAMP | Timestamp of last HRIS sync — used to detect stale records |

---

## Table 2 — `lms_training_activity`

**Source:** Cornerstone LMS content catalogue  
**Grain:** One row per training activity (course, module, curriculum, ILT programme)  
**Refreshed:** Daily  
**Used by:** All four use cases as the activity dimension

| Column | Data Type | Description |
|---|---|---|
| `activity_id` | VARCHAR(50) | Surrogate key — stable internal identifier for the training activity |
| `activity_external_id` | VARCHAR(50) | LMS platform identifier (e.g. Cornerstone course ID) |
| `activity_title` | VARCHAR(500) | Display title of the training activity |
| `activity_type` | VARCHAR(100) | Type of learning modality: Online Course, ILT, Curriculum, Assessment, Video, Document, Blended, Webinar |
| `category` | VARCHAR(200) | Content category or topic area (e.g. Compliance, Leadership, Technical, Safety) |
| `sub_category` | VARCHAR(200) | Secondary classification within the category |
| `is_compliance_training` | BOOLEAN | TRUE if this activity is flagged as mandatory compliance training |
| `is_assessment_required` | BOOLEAN | TRUE if the activity includes a required assessment or test |
| `passing_score` | DECIMAL(5,2) | Minimum score required to pass the assessment (0–100) |
| `expected_duration_minutes` | INTEGER | Vendor or admin-specified expected completion time in minutes |
| `credit_hours` | DECIMAL(6,2) | CE credit hours awarded upon completion — NULL if no CE credits attached |
| `vendor_id` | VARCHAR(50) | Foreign key to `lms_vendor` — NULL for internally produced content |
| `language` | VARCHAR(20) | Content language code (e.g. 'en-GB', 'fr-FR') |
| `version` | VARCHAR(20) | Content version identifier — used to track curriculum updates |
| `scorm_version` | VARCHAR(20) | SCORM package version (e.g. SCORM 1.2, SCORM 2004) — NULL for non-SCORM content |
| `is_active` | BOOLEAN | Whether the activity is currently available in the catalogue |
| `created_at` | TIMESTAMP | Date the activity was added to the LMS catalogue |
| `updated_at` | TIMESTAMP | Date the activity record was last modified |
| `retired_at` | TIMESTAMP | Date the activity was retired — NULL if active |

---

## Table 3 — `lms_enrollment`

**Source:** Cornerstone LMS  
**Grain:** One row per learner × activity assignment — one enrollment per assignment event  
**Refreshed:** Daily incremental  
**Used by:** Story 1 (compliance assignment load), Story 2 (activity completion), Story 3 (cert plan assignments), Story 4 (cancellations, cost denominator)

| Column | Data Type | Description |
|---|---|---|
| `enrollment_id` | VARCHAR(50) | Surrogate key — stable identifier for this enrollment record |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` |
| `assignment_type` | VARCHAR(50) | How the enrollment was created: Assigned (by admin), Self-enrolled, Plan-assigned, Curriculum-assigned, Manager-assigned |
| `is_self_directed` | BOOLEAN | TRUE if the learner enrolled voluntarily without an admin assignment |
| `assigned_by` | VARCHAR(50) | `learner_id` of the admin or manager who created the assignment — NULL for self-enrollments |
| `assigned_at` | TIMESTAMP | Timestamp when the enrollment was created |
| `due_date` | DATE | Deadline for completion — NULL if no deadline assigned |
| `due_date_type` | VARCHAR(50) | Type of deadline: Fixed, Rolling (days from assignment), Recurring |
| `status` | VARCHAR(50) | Current enrollment status: Not Started, In Progress, Completed, Overdue, Cancelled, Waived, Exempted |
| `is_compliance_required` | BOOLEAN | TRUE if this enrollment is a mandatory compliance requirement for the learner's role |
| `completion_id` | VARCHAR(50) | Foreign key to `lms_completion` — NULL until completed |
| `cancelled_at` | TIMESTAMP | Timestamp of cancellation — NULL if not cancelled |
| `cancellation_reason` | VARCHAR(500) | Free-text or coded reason for cancellation |
| `waived_by` | VARCHAR(50) | `learner_id` of approver who granted a waiver — NULL if not waived |
| `waived_at` | TIMESTAMP | Timestamp of waiver approval |
| `reminder_sent_count` | INTEGER | Number of automated reminder notifications sent for this enrollment |
| `last_reminder_sent_at` | TIMESTAMP | Timestamp of most recent reminder notification |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated timestamp |

---

## Table 4 — `lms_completion`

**Source:** Cornerstone LMS  
**Grain:** One row per completion event — a learner may complete the same activity more than once (recertification cycles)  
**Refreshed:** Daily incremental  
**Used by:** Story 1 (compliance completion quality), Story 2 (completion rate, quality signal), Story 4 (cost per completion denominator)

| Column | Data Type | Description |
|---|---|---|
| `completion_id` | VARCHAR(50) | Surrogate key |
| `enrollment_id` | VARCHAR(50) | Foreign key to `lms_enrollment` |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` — denormalised for query performance |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — denormalised |
| `completed_at` | TIMESTAMP | Timestamp when the completion status was recorded |
| `completion_type` | VARCHAR(50) | How completion was recorded: SCORM auto, Manual (admin), Test passed, Attendance marked |
| `total_sessions` | INTEGER | Number of distinct login sessions attributed to this enrollment before completion — key quality signal |
| `total_time_spent_minutes` | INTEGER | Total active time spent on the activity content in minutes |
| `first_launched_at` | TIMESTAMP | Timestamp when the learner first opened the activity content |
| `last_activity_at` | TIMESTAMP | Timestamp of the learner's most recent interaction with the content before completion |
| `days_to_complete` | INTEGER | Calendar days between enrollment creation date and completion date |
| `was_on_time` | BOOLEAN | TRUE if completed on or before `due_date` |
| `days_overdue_at_completion` | INTEGER | Number of days past due_date at time of completion — 0 or NULL if completed on time |
| `is_single_session_completion` | BOOLEAN | TRUE if `total_sessions` = 1 — used to detect checkbox/rushing behaviour |
| `is_under_expected_duration` | BOOLEAN | TRUE if `total_time_spent_minutes` < 50% of `lms_training_activity.expected_duration_minutes` |
| `score` | DECIMAL(5,2) | Final recorded score — NULL if no assessment attached |
| `passed` | BOOLEAN | TRUE if score ≥ `lms_training_activity.passing_score` — NULL if no assessment |
| `credit_hours_awarded` | DECIMAL(6,2) | CE credit hours awarded for this completion — NULL if no CE credits |
| `created_at` | TIMESTAMP | Record creation timestamp |

---

## Table 5 — `lms_assessment_attempt`

**Source:** Cornerstone LMS (SCORM interaction log + native assessment engine)  
**Grain:** One row per assessment attempt per learner — multiple rows per enrollment when retries occur  
**Refreshed:** Daily incremental  
**Used by:** Story 2 (pass rate, avg attempts, score distribution, retry analysis)

| Column | Data Type | Description |
|---|---|---|
| `attempt_id` | VARCHAR(50) | Surrogate key |
| `enrollment_id` | VARCHAR(50) | Foreign key to `lms_enrollment` |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` — denormalised |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — denormalised |
| `attempt_number` | INTEGER | Sequence number of this attempt (1 = first, 2 = second retry, etc.) |
| `attempted_at` | TIMESTAMP | Timestamp when the attempt was started |
| `completed_at` | TIMESTAMP | Timestamp when the attempt was submitted |
| `duration_minutes` | INTEGER | Time taken to complete this attempt in minutes |
| `score` | DECIMAL(5,2) | Raw score achieved (0–100) |
| `passed` | BOOLEAN | TRUE if score ≥ passing threshold for this activity |
| `status` | VARCHAR(50) | Attempt outcome: Passed, Failed, Incomplete, Timed Out |
| `question_count` | INTEGER | Number of questions in this assessment attempt |
| `correct_count` | INTEGER | Number of questions answered correctly |
| `incorrect_count` | INTEGER | Number of questions answered incorrectly |
| `skipped_count` | INTEGER | Number of questions skipped or unanswered |
| `sessions_before_attempt` | INTEGER | Number of content sessions completed before this assessment attempt — key signal for engagement depth prior to testing |
| `time_in_content_before_attempt_minutes` | INTEGER | Total content time logged before attempting the assessment |
| `is_first_attempt` | BOOLEAN | TRUE if `attempt_number` = 1 |
| `created_at` | TIMESTAMP | Record creation timestamp |

---

## Table 6 — `lms_session_log`

**Source:** SSO / Cornerstone LMS session events  
**Grain:** One row per user session — a session begins at login and ends at logout or timeout  
**Refreshed:** Daily incremental (near-real-time optional)  
**Used by:** Story 1 (login trend, session-to-user ratio, engagement signal), Story 2 (sessions before assessment), Story 3 (at-risk population engagement)

| Column | Data Type | Description |
|---|---|---|
| `session_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `session_start_at` | TIMESTAMP | Timestamp of login / session initiation |
| `session_end_at` | TIMESTAMP | Timestamp of logout or session timeout — NULL if session is still active |
| `duration_minutes` | INTEGER | Session duration in minutes — computed from start/end timestamps |
| `session_date` | DATE | Calendar date of the session — denormalised for daily aggregation |
| `week_start_date` | DATE | ISO week start date (Monday) — for weekly aggregation |
| `device_type` | VARCHAR(50) | Device category: Desktop, Mobile, Tablet |
| `access_method` | VARCHAR(50) | How the session was initiated: Direct, SSO, Mobile App, API |
| `activities_accessed` | INTEGER | Count of distinct training activities accessed during this session |
| `activity_ids_accessed` | ARRAY(VARCHAR) | List of `activity_id` values accessed in this session — for session-to-activity linking |
| `is_active_session` | BOOLEAN | TRUE if activities were accessed (vs. login with no content interaction) |
| `source_ip_region` | VARCHAR(100) | Geographic region derived from IP — NULL if unavailable or privacy-blocked |
| `created_at` | TIMESTAMP | Record creation timestamp |

---

## Table 7 — `lms_ilt_session`

**Source:** Cornerstone LMS ILT module  
**Grain:** One row per ILT class session offering (a physical or virtual class with a scheduled date and seat count)  
**Refreshed:** Daily  
**Used by:** Story 3 (cert renewal capacity), Story 4 (ILT capacity utilisation, approval backlog)

| Column | Data Type | Description |
|---|---|---|
| `ilt_session_id` | VARCHAR(50) | Surrogate key |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — the parent ILT programme this session belongs to |
| `session_title` | VARCHAR(500) | Display title for this specific session offering |
| `instructor_id` | VARCHAR(50) | Foreign key to `lms_learner` (instructor is also a user) — primary instructor |
| `co_instructor_id` | VARCHAR(50) | Secondary instructor — NULL if single instructor |
| `session_date` | DATE | Scheduled date of the session |
| `start_time` | TIME | Scheduled start time |
| `end_time` | TIME | Scheduled end time |
| `duration_hours` | DECIMAL(4,2) | Session duration in hours |
| `delivery_format` | VARCHAR(50) | Classroom, Virtual (Zoom/Teams), Hybrid, Self-paced ILT |
| `location` | VARCHAR(200) | Physical room or virtual meeting URL |
| `max_capacity` | INTEGER | Maximum number of registered learners allowed |
| `registered_count` | INTEGER | Number of learners currently registered (snapshot at last refresh) |
| `attended_count` | INTEGER | Number of learners marked as attended — populated post-session |
| `no_show_count` | INTEGER | Registered learners who did not attend — populated post-session |
| `waiting_list_count` | INTEGER | Number of learners on the waiting list for this session |
| `capacity_utilisation_rate` | DECIMAL(5,4) | `attended_count / max_capacity` — NULL until session completes |
| `status` | VARCHAR(50) | Session status: Draft, Pending Approval, Open for Booking, Fully Booked, Completed, Cancelled |
| `approval_required` | BOOLEAN | TRUE if this session requires manager or admin approval before learner can register |
| `approval_submitted_at` | TIMESTAMP | Timestamp when session was submitted for approval |
| `approval_completed_at` | TIMESTAMP | Timestamp when approval decision was made — NULL if pending |
| `approved_by` | VARCHAR(50) | `learner_id` of approver |
| `cancellation_reason` | VARCHAR(500) | Reason if session was cancelled — NULL otherwise |
| `vendor_id` | VARCHAR(50) | Foreign key to `lms_vendor` — NULL for internally delivered sessions |
| `cost_per_session` | DECIMAL(12,2) | Fixed delivery cost for this session regardless of attendance |
| `cost_per_seat` | DECIMAL(10,2) | Per-learner cost if charged by seat — NULL if fixed-cost model |
| `currency` | VARCHAR(10) | Currency code (e.g. GBP, USD, EUR) |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated timestamp |

---

## Table 8 — `lms_ilt_registration`

**Source:** Cornerstone LMS ILT module  
**Grain:** One row per learner × ILT session registration — a learner may register, cancel, and re-register for the same session (generating multiple rows)  
**Refreshed:** Daily incremental  
**Used by:** Story 3 (renewal access, waiting list analysis), Story 4 (no-show rate, cancellation waste, churn detection)

| Column | Data Type | Description |
|---|---|---|
| `registration_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `ilt_session_id` | VARCHAR(50) | Foreign key to `lms_ilt_session` |
| `enrollment_id` | VARCHAR(50) | Foreign key to `lms_enrollment` — the enrollment this ILT registration satisfies |
| `registration_type` | VARCHAR(50) | Registered, Waiting List, Pending Approval |
| `registered_at` | TIMESTAMP | Timestamp of registration |
| `registration_source` | VARCHAR(50) | How the registration was created: Self-registered, Manager-registered, Admin-registered, Auto-enrolled |
| `status` | VARCHAR(50) | Current status: Registered, Attended, No-Show, Cancelled, Waitlisted, Moved |
| `attended` | BOOLEAN | TRUE if learner was marked present — populated post-session |
| `attendance_marked_at` | TIMESTAMP | Timestamp when attendance was recorded |
| `no_show` | BOOLEAN | TRUE if learner was registered but did not attend |
| `cancelled_at` | TIMESTAMP | Timestamp of cancellation — NULL if not cancelled |
| `cancellation_source` | VARCHAR(50) | Who cancelled: Learner, Manager, Admin, System |
| `cancellation_reason` | VARCHAR(500) | Coded or free-text reason for cancellation |
| `days_before_session_cancelled` | INTEGER | Number of days before the session date the cancellation was made — used to identify late cancellations that incur full cost |
| `is_late_cancellation` | BOOLEAN | TRUE if cancelled within the late-cancellation window (typically ≤ 2 business days before session) |
| `is_double_booked` | BOOLEAN | TRUE if learner had another registration for the same `activity_id` at the time of cancellation — proxy for waiting list churn |
| `moved_to_session_id` | VARCHAR(50) | If the learner was moved to a different session, the target `ilt_session_id` — used to track rescheduling |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 9 — `lms_certification`

**Source:** Cornerstone LMS certification module  
**Grain:** One row per certification definition  
**Refreshed:** Daily  
**Used by:** Story 3 (cert definition, validity window, renewal pathway)

| Column | Data Type | Description |
|---|---|---|
| `certification_id` | VARCHAR(50) | Surrogate key |
| `certification_name` | VARCHAR(500) | Display name of the certification |
| `certification_type` | VARCHAR(100) | Internal, External Regulatory, Professional Body, Vendor, Safety |
| `issuing_body` | VARCHAR(200) | Organisation that grants or recognises the certification — NULL for internal certs |
| `is_regulatory_required` | BOOLEAN | TRUE if required by law or regulation for the associated role |
| `validity_period_months` | INTEGER | Number of months the certification remains valid before renewal is required |
| `renewal_pathway` | VARCHAR(100) | How renewal is achieved: ILT Only, CE Credits, Self-directed, Exam, Mixed |
| `required_ce_credits` | DECIMAL(6,2) | CE credits required for renewal — NULL if ILT-only pathway |
| `renewal_notice_days` | INTEGER | Days before expiry that renewal reminders are triggered |
| `associated_activity_ids` | ARRAY(VARCHAR) | `activity_id` values that fulfil this certification requirement |
| `applicable_job_families` | ARRAY(VARCHAR) | Job family codes that are required or eligible to hold this certification |
| `is_active` | BOOLEAN | Whether the certification is currently in use |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 10 — `lms_learner_certification`

**Source:** Cornerstone LMS certification module  
**Grain:** One row per learner × certification assignment — includes history (previous completions, expirations, renewals)  
**Refreshed:** Daily incremental  
**Used by:** Story 3 — all certification KPIs derive from this table

| Column | Data Type | Description |
|---|---|---|
| `learner_cert_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `certification_id` | VARCHAR(50) | Foreign key to `lms_certification` |
| `assigned_at` | TIMESTAMP | Timestamp when this certification was assigned to the learner |
| `assignment_source` | VARCHAR(50) | How assigned: Job Role Rule, Manual Admin, Onboarding Workflow |
| `status` | VARCHAR(50) | Current status: Not Started, In Progress, Completed, Expired, Overdue, Waived |
| `issued_at` | TIMESTAMP | Timestamp when the certification was first awarded — NULL until earned |
| `current_expiry_date` | DATE | Date the current certification instance expires — NULL if not yet earned |
| `previous_expiry_date` | DATE | Expiry date of the previous certification cycle — used to track renewal history |
| `renewal_count` | INTEGER | Number of times this certification has been renewed — 0 for first-time earners |
| `days_until_expiry` | INTEGER | Computed: `current_expiry_date - CURRENT_DATE` — negative if already expired |
| `is_expiring_within_30d` | BOOLEAN | TRUE if expiry is within 30 calendar days |
| `is_expiring_within_60d` | BOOLEAN | TRUE if expiry is within 60 calendar days |
| `is_expiring_within_90d` | BOOLEAN | TRUE if expiry is within 90 calendar days |
| `is_overdue` | BOOLEAN | TRUE if `current_expiry_date < CURRENT_DATE` and not renewed |
| `days_overdue` | INTEGER | Number of days past expiry — 0 or NULL if not overdue |
| `on_waiting_list` | BOOLEAN | TRUE if learner is currently on a waiting list for an ILT renewal session |
| `waiting_list_ilt_session_id` | VARCHAR(50) | `ilt_session_id` the learner is waiting for — NULL if not on waiting list |
| `renewal_in_progress` | BOOLEAN | TRUE if learner has an active enrollment in a renewal activity |
| `completion_id` | VARCHAR(50) | Foreign key to `lms_completion` for the most recent completion event |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 11 — `lms_ce_credit_log`

**Source:** Cornerstone LMS / external CE tracking integration  
**Grain:** One row per CE credit earning event — a learner earns credits from multiple activities  
**Refreshed:** Daily incremental  
**Used by:** Story 3 (CE credit acquired, shortfall, compliance rate)

| Column | Data Type | Description |
|---|---|---|
| `ce_credit_event_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `certification_id` | VARCHAR(50) | Foreign key to `lms_certification` — which certification these credits count toward |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — the activity that generated the credit |
| `completion_id` | VARCHAR(50) | Foreign key to `lms_completion` — the completion event that triggered the credit |
| `credits_earned` | DECIMAL(6,2) | Number of CE credits awarded for this event |
| `credit_type` | VARCHAR(100) | Credit category (e.g. CPD, CPE, CLE, CME) — relevant for regulated professions |
| `earned_at` | TIMESTAMP | Timestamp when credits were awarded |
| `expiry_date` | DATE | Date these specific credits expire — some CE programmes expire unused credits |
| `credit_period_start` | DATE | Start of the renewal period these credits apply to |
| `credit_period_end` | DATE | End of the renewal period these credits must be earned within |
| `is_approved` | BOOLEAN | Whether the credit has been approved (some external CE requires approval) |
| `approved_by` | VARCHAR(50) | `learner_id` of approver — NULL for auto-approved |
| `source` | VARCHAR(100) | Credit source: Internal Activity, External Course, Conference, Self-Reported |
| `created_at` | TIMESTAMP | Record creation timestamp |

---

## Table 12 — `lms_training_plan`

**Source:** Cornerstone LMS development planning module  
**Grain:** One row per training plan definition  
**Refreshed:** Daily  
**Used by:** Story 2 (plan completion as confounder), Story 3 (structured renewal pathway)

| Column | Data Type | Description |
|---|---|---|
| `plan_id` | VARCHAR(50) | Surrogate key |
| `plan_name` | VARCHAR(500) | Display name of the training plan |
| `plan_type` | VARCHAR(100) | Type: Onboarding, Compliance, Capability Development, Certification Renewal, Mandatory |
| `plan_duration_days` | INTEGER | Total number of calendar days from assignment to expected completion |
| `goal_count` | INTEGER | Number of learning goals defined in this plan |
| `activity_count` | INTEGER | Number of individual activities included in this plan |
| `target_job_families` | ARRAY(VARCHAR) | Job family codes this plan is designed for |
| `is_compliance_plan` | BOOLEAN | TRUE if this plan contains compliance-mandatory content |
| `is_active` | BOOLEAN | Whether the plan is currently available for assignment |
| `created_by` | VARCHAR(50) | `learner_id` of admin who created the plan |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 13 — `lms_training_plan_enrollment`

**Source:** Cornerstone LMS  
**Grain:** One row per learner × training plan assignment  
**Refreshed:** Daily incremental  
**Used by:** Story 2 (plan completion % as confounder control), Story 3 (structured renewal tracking)

| Column | Data Type | Description |
|---|---|---|
| `plan_enrollment_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `plan_id` | VARCHAR(50) | Foreign key to `lms_training_plan` |
| `assigned_at` | TIMESTAMP | Timestamp when the plan was assigned |
| `assigned_by` | VARCHAR(50) | `learner_id` of assigning admin — NULL if auto-assigned by job role rule |
| `due_date` | DATE | Plan completion deadline |
| `status` | VARCHAR(50) | Not Started, In Progress, Completed, Overdue, Cancelled |
| `activities_completed` | INTEGER | Number of activities within this plan the learner has completed (snapshot) |
| `activities_total` | INTEGER | Total number of activities in this plan |
| `completion_pct` | DECIMAL(5,4) | `activities_completed / activities_total` — snapshot percentage |
| `completed_at` | TIMESTAMP | Timestamp when all plan activities were completed — NULL until done |
| `was_on_time` | BOOLEAN | TRUE if completed on or before `due_date` |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 14 — `lms_evaluation_response`

**Source:** Cornerstone LMS evaluation / Level 1 feedback module  
**Grain:** One row per evaluation form submission  
**Refreshed:** Daily incremental  
**Used by:** Story 2 (eval completion rate, post-training engagement signal)

| Column | Data Type | Description |
|---|---|---|
| `eval_response_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `enrollment_id` | VARCHAR(50) | Foreign key to `lms_enrollment` — the training enrollment being evaluated |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — denormalised |
| `evaluation_form_id` | VARCHAR(50) | Identifier for the evaluation form template used |
| `submitted_at` | TIMESTAMP | Timestamp of evaluation submission |
| `days_after_completion` | INTEGER | Days between training completion and evaluation submission |
| `overall_satisfaction_score` | DECIMAL(3,1) | Overall rating (e.g. 1–5 or 1–10 scale) |
| `content_relevance_score` | DECIMAL(3,1) | Rating of content relevance to role |
| `instructor_effectiveness_score` | DECIMAL(3,1) | Rating of instructor or facilitator — NULL for self-directed content |
| `knowledge_gain_score` | DECIMAL(3,1) | Learner's self-reported assessment of knowledge gained |
| `would_recommend` | BOOLEAN | Whether the learner would recommend this training to a colleague |
| `free_text_feedback` | TEXT | Open-text feedback — raw, unprocessed |
| `is_complete` | BOOLEAN | TRUE if all required evaluation questions were answered |
| `question_count_answered` | INTEGER | Number of evaluation questions answered |
| `question_count_total` | INTEGER | Total number of evaluation questions on the form |
| `created_at` | TIMESTAMP | Record creation timestamp |

---

## Table 15 — `lms_training_cost`

**Source:** Finance / ERP system (Workday Finance or NetSuite)  
**Grain:** One row per cost allocation event — may be per-session (fixed) or per-seat (variable)  
**Refreshed:** Monthly or upon invoice processing  
**Used by:** Story 4 — all cost and ROI metrics derive from this table

| Column | Data Type | Description |
|---|---|---|
| `cost_event_id` | VARCHAR(50) | Surrogate key |
| `cost_type` | VARCHAR(100) | Type of cost: ILT Session Delivery, Vendor License, Content Development, Platform Fee, Instructor Time, Facility, Travel, Cancellation Fee, No-Show Fee |
| `ilt_session_id` | VARCHAR(50) | Foreign key to `lms_ilt_session` — NULL for non-ILT costs |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — NULL for platform-level costs |
| `vendor_id` | VARCHAR(50) | Foreign key to `lms_vendor` — NULL for internally incurred costs |
| `cost_amount` | DECIMAL(14,2) | Cost in local currency |
| `currency` | VARCHAR(10) | Currency code (e.g. GBP, USD, EUR) |
| `cost_amount_usd` | DECIMAL(14,2) | Cost normalised to USD using period exchange rate — for cross-currency reporting |
| `cost_period_start` | DATE | Start of the period this cost applies to (for recurring/licence fees) |
| `cost_period_end` | DATE | End of the period this cost applies to |
| `invoice_date` | DATE | Date of vendor invoice |
| `invoice_reference` | VARCHAR(100) | Invoice or purchase order reference number |
| `cost_centre` | VARCHAR(50) | Finance cost centre receiving this charge |
| `is_wasted_cost` | BOOLEAN | TRUE if this cost was incurred without a training completion (e.g. no-show fee, late cancellation) |
| `wasted_cost_reason` | VARCHAR(100) | Reason for waste classification: No Show, Late Cancellation, Session Cancelled, Unused License |
| `learner_count_attributed` | INTEGER | Number of learners this cost is attributed to — used to compute per-learner cost |
| `cost_per_learner` | DECIMAL(10,2) | `cost_amount / learner_count_attributed` — NULL for fixed platform costs |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 16 — `lms_vendor`

**Source:** Vendor Management / Procurement system  
**Grain:** One row per vendor  
**Refreshed:** Weekly  
**Used by:** Story 4 (vendor efficiency analysis, cost per hour by vendor)

| Column | Data Type | Description |
|---|---|---|
| `vendor_id` | VARCHAR(50) | Surrogate key |
| `vendor_name` | VARCHAR(200) | Vendor display name |
| `vendor_type` | VARCHAR(100) | Content Provider, ILT Delivery Partner, Platform Vendor, Assessment Provider, Certification Body |
| `contract_start_date` | DATE | Start date of current vendor contract |
| `contract_end_date` | DATE | End date of current vendor contract |
| `contracted_rate_per_hour` | DECIMAL(10,2) | Hourly rate for delivered learning — NULL for per-seat or subscription models |
| `contracted_rate_per_seat` | DECIMAL(10,2) | Per-seat cost for ILT or instructor-led sessions — NULL for hourly models |
| `subscription_cost_annual` | DECIMAL(14,2) | Annual licence or subscription cost — NULL for pay-per-use vendors |
| `currency` | VARCHAR(10) | Contract currency |
| `cancellation_window_days` | INTEGER | Number of business days before session at which cancellation incurs full charge |
| `is_preferred_vendor` | BOOLEAN | TRUE if this vendor is on the preferred supplier list |
| `is_active` | BOOLEAN | Whether the vendor relationship is currently active |
| `primary_contact_name` | VARCHAR(200) | Account manager name |
| `primary_contact_email` | VARCHAR(200) | Account manager email |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last updated |

---

## Table 17 — `lms_cancellation_log`

**Source:** Cornerstone LMS — cancellation events extracted from enrollment and ILT registration tables  
**Grain:** One row per cancellation event  
**Refreshed:** Daily incremental  
**Used by:** Story 4 (cancellation cost quantification, late cancellation identification, churn detection)

| Column | Data Type | Description |
|---|---|---|
| `cancellation_id` | VARCHAR(50) | Surrogate key |
| `learner_id` | VARCHAR(50) | Foreign key to `lms_learner` |
| `enrollment_id` | VARCHAR(50) | Foreign key to `lms_enrollment` — NULL if ILT-only cancellation |
| `ilt_registration_id` | VARCHAR(50) | Foreign key to `lms_ilt_registration` — NULL if course-level cancellation |
| `ilt_session_id` | VARCHAR(50) | Foreign key to `lms_ilt_session` — NULL if course-level cancellation |
| `activity_id` | VARCHAR(50) | Foreign key to `lms_training_activity` — denormalised |
| `cancelled_at` | TIMESTAMP | Timestamp of cancellation |
| `cancellation_source` | VARCHAR(50) | Who cancelled: Learner, Manager, Admin, System |
| `cancellation_reason_code` | VARCHAR(50) | Coded reason: Scheduling Conflict, Role Change, No Longer Required, Manager Request, Personal, System Auto-Cancel |
| `cancellation_reason_text` | VARCHAR(500) | Free-text reason — NULL if reason code is sufficient |
| `session_date` | DATE | Scheduled date of the ILT session being cancelled — NULL for course cancellations |
| `days_before_session` | INTEGER | Days between cancellation timestamp and session date — negative means session already passed |
| `is_late_cancellation` | BOOLEAN | TRUE if `days_before_session` ≤ vendor's `cancellation_window_days` |
| `estimated_cost_incurred` | DECIMAL(10,2) | Estimated cost incurred due to this cancellation (full charge if late, partial if early) |
| `was_replaced` | BOOLEAN | TRUE if another learner filled the vacated seat before the session date |
| `replaced_by_learner_id` | VARCHAR(50) | `learner_id` of the replacement learner — NULL if seat remained empty |
| `created_at` | TIMESTAMP | Record creation timestamp |

---

## Metric Derivation Reference

This table shows which silver tables are joined to compute each of the key gold-layer metrics.

| Metric | Primary Tables | Join Keys | Key Computed Fields |
|---|---|---|---|
| **Compliance Rate** | `lms_enrollment`, `lms_learner` | `enrollment_id`, `learner_id` | `is_compliance_required = TRUE` · status = Completed / not Overdue |
| **Overdue Trainings** | `lms_enrollment` | — | `status = 'Overdue'` · `due_date < CURRENT_DATE` |
| **Missed Deadlines** | `lms_enrollment` | — | `due_date < CURRENT_DATE AND status != 'Completed'` |
| **Session-to-User Ratio** | `lms_session_log` | `learner_id` | `COUNT(session_id) / COUNT(DISTINCT learner_id)` over period |
| **Weekly Login Trend** | `lms_session_log` | — | `COUNT(DISTINCT learner_id) GROUP BY week_start_date` |
| **Completion Rate** | `lms_enrollment`, `lms_completion` | `enrollment_id` | `COUNT(completed) / COUNT(assigned)` |
| **Single-Session Completion %** | `lms_completion` | — | `COUNT(is_single_session_completion = TRUE) / COUNT(*)` |
| **Pass Rate** | `lms_assessment_attempt` | — | `COUNT(passed = TRUE, is_first_attempt = TRUE) / COUNT(DISTINCT enrollment_id)` |
| **Avg Attempts per Learner** | `lms_assessment_attempt` | `learner_id` | `COUNT(attempt_id) / COUNT(DISTINCT learner_id)` |
| **Score Distribution** | `lms_assessment_attempt` | — | `score` bucketed into bands |
| **Self-Directed Ratio** | `lms_enrollment` | — | `COUNT(is_self_directed = TRUE) / COUNT(*)` |
| **Eval Completion Rate** | `lms_evaluation_response`, `lms_completion` | `enrollment_id` | `COUNT(eval submitted) / COUNT(completions)` |
| **Cert Compliance Rate** | `lms_learner_certification` | — | `COUNT(status = 'Completed' AND NOT expired) / COUNT(assigned)` |
| **Certs Expiring Soon** | `lms_learner_certification` | — | `COUNT(is_expiring_within_30d = TRUE)` etc. |
| **Cert Overdue** | `lms_learner_certification` | — | `COUNT(is_overdue = TRUE)` |
| **ILT Waiting List Count** | `lms_ilt_registration` | `ilt_session_id` | `COUNT(registration_type = 'Waiting List')` |
| **ILT Attendance Rate** | `lms_ilt_registration`, `lms_ilt_session` | `ilt_session_id` | `SUM(attended_count) / SUM(registered_count)` |
| **ILT Capacity Utilisation** | `lms_ilt_session` | — | `SUM(attended_count) / SUM(max_capacity)` |
| **CE Credit Shortfall** | `lms_ce_credit_log`, `lms_certification` | `learner_id`, `certification_id` | `required_ce_credits - SUM(credits_earned)` per learner |
| **No-Show Rate** | `lms_ilt_registration` | — | `SUM(no_show = TRUE) / COUNT(registered)` |
| **Training Cost per Learner** | `lms_training_cost`, `lms_completion` | `activity_id` | `SUM(cost_amount) / COUNT(DISTINCT learner completions)` |
| **Wasted Cost (No-Shows)** | `lms_training_cost` | — | `SUM(cost_amount WHERE is_wasted_cost = TRUE AND wasted_cost_reason = 'No Show')` |
| **Vendor Cost per Hour** | `lms_training_cost`, `lms_ilt_session`, `lms_vendor` | `vendor_id` | `SUM(cost_amount) / SUM(attended_count × duration_hours)` |
