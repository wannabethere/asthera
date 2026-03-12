# CSOD Learn MDL Files Reference

Reference for enriching `csod_project_metadata.json` with CSOD Learn (Cornerstone LMS) schema metadata.

**Source:** `/Users/sameermangalampalli/Downloads/CSOD_Learn_mdl_files`  
**Format:** `.mdl.json` files (catalog, schema, models with columns and properties)

---

## 1. Top-Level Categories

| Category | Subcategories | Use For |
|----------|---------------|---------|
| **Learning & Training** | Training Catalog, Transcript, Assignments, Curriculum, ILT, SCORM, Finance, Models | Training completion, compliance, effectiveness, ROI |
| **Users & HR Management** | User Core, OU, User-OU, Termination, Dynamic Relation | User context, org hierarchy, audience segmentation |
| **Assessment & Q&A** | Assessments, Q&A | Knowledge checks, assessments, certifications |
| **Localization & Metadata** | Timezone, Currency, Culture, Language | Multi-tenancy, localization |
| **Custom Fields (CF)** | User CF, OU CF, Training CF, etc. | Extensible attributes |

---

## 2. Learning & Training — Tables by Subcategory

### 2.1 Training Catalog (LO) — Learning Objects

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_core` | object_id | Training/course catalog (master) |
| `training_local_core` | — | Localized training names/descriptions |
| `training_type_core` | — | Course type (online, ILT, etc.) |
| `training_type_local_core` | — | Localized type labels |
| `training_relationship_core` | — | Course relationships (prerequisite, etc.) |
| `training_relationship_type_core` | — | Relationship types |
| `training_equivalency_core` | — | Course equivalencies |
| `training_contact_core` | — | Training contact/owner |
| `training_material_type_core` | — | Material types (SCORM, video, etc.) |
| `training_provider_core` | — | Training providers/vendors |
| `training_provider_instructor_membership_core` | — | Provider-instructor mapping |
| `subject_core` | — | Subject taxonomy |
| `subject_training_core` | — | Subject–training mapping |
| `subject_equivalent_core` | — | Subject equivalencies |
| `course_rating_core` | — | Course ratings |
| `online_course_protocol_local_core` | — | Online protocol types |

**Metadata enrichment:** `categories` → `training_completion`, `learning_effectiveness`, `kpi_recommendations`  
**Focus areas:** `ld_training`, `ld_engagement`

### 2.2 Transcript & Statuses — Completion & Status

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `transcript_core` | reg_num | Training transcript (user–course completion) |
| `transcript_assignment_core` | — | Transcript assignments |
| `transcript_src_assignment_core` | — | Source assignment for transcript |
| `transcript_status_local_core` | — | Status labels (Completed, In Progress, etc.) |
| `transcript_action_reason_local_core` | — | Action reason labels |
| `transcript_delivery_method_local_core` | — | Delivery method (online, ILT, etc.) |
| `transcript_origin_type_local_core` | — | Origin type (assignment, self-enroll, etc.) |
| `training_status_type_local_core` | — | Training status types |
| `training_exemption_reason_local_core` | — | Exemption reasons |
| `training_removal_reason_local_core` | — | Removal reasons |

**Metadata enrichment:** `categories` → `training_completion`, `compliance_training`, `mandatory_training`, `overdue_tracking`  
**Focus areas:** `ld_training`, `compliance_training`  
**Key for:** Completion rates, overdue metrics, compliance dashboards

### 2.3 Assignments (LAT) — Learning Assignments

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_assignment_core` | — | Training assignments (master) |
| `training_assignment_detail_core` | — | Assignment details |
| `training_assignment_lat_core` | — | LAT-specific assignment data |
| `training_assignment_user_core` | — | User–assignment mapping |
| `training_requirement_tag_core` | — | Requirement tags |
| `training_requirement_tag_category_core` | — | Requirement tag categories |
| `training_availability_by_user_core` | — | User availability |
| `training_availability_by_ou_core` | — | OU availability |

**Metadata enrichment:** `categories` → `training_completion`, `compliance_training`, `mandatory_training`  
**Focus areas:** `ld_training`, `compliance_training`  
**Key for:** Assigned vs completed, overdue assignments

### 2.4 Curriculum & Bundles

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_bundle_core` | — | Training bundles |
| `training_bundle_manifest_core` | — | Bundle contents |
| `curriculum_structure_core` | — | Curriculum structure |
| `curriculum_due_date_type_local_core` | — | Due date types |

**Metadata enrichment:** `categories` → `training_completion`, `certification_tracking`  
**Focus areas:** `ld_training`

### 2.5 ILT (Event-Session) — Instructor-Led Training

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_ilt_session_core` | — | ILT sessions/events |
| `training_ilt_facility_core` | — | Facilities |
| `training_ilt_facility_type_local_core` | — | Facility types |
| `training_part2_core` | — | Session parts |
| `training_part_local_core` | — | Localized part info |
| `training_part_attendance_core` | — | Attendance |
| `training_part_instructor_core` | — | Session instructors |
| `instructor_core` | — | Instructor master |

**Metadata enrichment:** `categories` → `training_roi`, `cost_efficiency`, `no_shows`, `ilt_utilization`  
**Focus areas:** `ld_operations`  
**Key for:** ILT cost, no-shows, utilization

### 2.6 SCORM — eLearning Tracking

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_scorm_core` | — | SCORM content |
| `scorm_session` | — | SCORM sessions |
| `scorm_subsession` | — | Sub-sessions |
| `scorm_subsession_interaction` | — | Interactions |
| `scorm_subsession_interaction_correct_response` | — | Correct responses |
| `scorm2004_activity_session_history` | — | SCORM 2004 activity history |
| `scorm2004_interaction_history` | — | SCORM 2004 interaction history |

**Metadata enrichment:** `categories` → `learning_effectiveness`, `knowledge_retention`  
**Focus areas:** `ld_engagement`

### 2.7 Training Models

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_model_core` | — | Training models |
| `training_model_local_core` | — | Localized model info |
| `training_model_training_object_core` | — | Model–training mapping |

**Metadata enrichment:** `categories` → `training_completion`, `learning_effectiveness`

### 2.8 Training Finance-E-Commerce

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `training_purchase_core` | — | Purchases |
| `training_purchase_line_item_core` | — | Line items |
| `training_purchase_payer_core` | — | Payers |
| `training_purchase_payment_type_core` | — | Payment types |
| `training_license_core` | — | Licenses |
| `training_purchaser_overrides_core` | — | Purchaser overrides |

**Metadata enrichment:** `categories` → `training_roi`, `cost_efficiency`, `vendor_efficiency`  
**Focus areas:** `ld_operations`

---

## 3. Users & HR Management

### 3.1 User Core Details

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `users_core` | — | User master |
| `user_login_core` | — | Login info |
| `address_core` | — | Addresses |
| `user_category_local_core` | — | User category labels |
| `user_sub_category_local_core` | — | Sub-category labels |
| `user_type_local_core` | — | User type labels |
| `user_employment_status_local_core` | — | Employment status |
| `user_leave_reason_local_core` | — | Leave reasons |

**Metadata enrichment:** User context for segmentation, audience filters

### 3.2 Organizational Units (OU)

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `ou_core` | — | OU master |
| `ou_local_core` | — | Localized OU names |
| `ou_type_core` | — | OU types |
| `ou_type_local_core` | — | Localized type labels |
| `ou_address_core` | — | OU addresses |
| `ou_hierarchy_core` | — | OU hierarchy |

**Metadata enrichment:** Org hierarchy for roll-up, department filters

### 3.3 User-OU Association

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `user_ou_core` | — | User–OU association |
| `user_ou_multi_core` | — | Multi-OU |
| `user_ou_pivoted_core` | — | Pivoted OU view |
| `user_ou_status_local_core` | — | Status labels |

**Metadata enrichment:** User–org mapping for drill-down

### 3.4 Termination

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `user_termination_reason_core` | — | Termination reasons |
| `user_termination_reason_local_core` | — | Localized labels |
| `user_termination_reason_category_core` | — | Reason categories |
| `user_termination_reason_category_local_core` | — | Localized categories |

**Metadata enrichment:** Exclude terminated users in metrics

---

## 4. Assessment & Q&A

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `assessment_test_core` | — | Assessment tests |
| `assessment_type_core` | — | Assessment types |
| `assessment_result_core` | — | Assessment results |
| `assessment_response_core` | — | Responses |
| `assessment_evaluation_core` | — | Evaluations |
| `qna_container_core` | — | Q&A containers |
| `qna_structure_core` | — | Q&A structure |
| `qna_question_core` | — | Questions |
| `qna_question_category_core` | — | Question categories |
| `qna_answer_bank_core` | — | Answer bank |
| `qna_correct_answer_core` | — | Correct answers |
| `qna_target_person_core` | — | Target persons |

**Metadata enrichment:** `categories` → `certification_tracking`, `knowledge_retention`, `learning_effectiveness`  
**Focus areas:** `ld_engagement`, `compliance_training`

---

## 5. Localization & Metadata

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| `timezone_core` | — | Timezones |
| `timezone_local_core` | — | Localized timezone labels |
| `currency_core` | — | Currencies |
| `culture_core` | — | Cultures |
| `language_core` | — | Languages |
| `compensation_type_local_core` | — | Compensation types |

**Metadata enrichment:** Multi-tenant, localization filters

---

## 6. Custom Fields (CF)

| Table | Purpose |
|-------|---------|
| `users_cf_core` | User custom fields |
| `user_cf_enum_local2_core` | User CF enum values |
| `ou_cf_text_local_core` | OU custom fields |
| `devplan_cf_core`, `devplan_cf_enum_local2_core` | Development plan CF |
| `job_requisition_cf_core`, `job_requisition_template_core` | Job requisition CF |
| `training_forecast_cf_enum_local2_core` | Training forecast CF |
| etc. | Other CF tables |

**Metadata enrichment:** Extensible attributes for project-specific metrics

---

## 7. Suggested Enrichments for csod_project_metadata.json

### 7.1 Add `mdl_tables` per project

```json
{
  "project_id": "proj_csod_compliance_001",
  "mdl_tables": {
    "primary": ["transcript_core", "training_assignment_core", "training_core"],
    "supporting": ["users_core", "ou_core", "user_ou_core", "transcript_status_local_core"],
    "optional": ["training_ilt_session_core", "assessment_result_core"]
  }
}
```

### 7.2 Add `table_to_category` mapping

```json
{
  "table_to_category": {
    "transcript_core": ["training_completion", "compliance_training", "overdue_tracking"],
    "training_assignment_core": ["training_completion", "mandatory_training"],
    "training_ilt_session_core": ["training_roi", "no_shows", "ilt_utilization"],
    "assessment_result_core": ["certification_tracking", "knowledge_retention"]
  }
}
```

### 7.3 Add `key_columns` for common metrics

```json
{
  "key_columns": {
    "transcript_core": ["reg_num", "user_id", "object_id", "training_status_id", "completed_date", "registration_date"],
    "training_assignment_core": ["training_assignment_id", "user_id", "object_id", "due_date", "status"]
  }
}
```

### 7.4 Naming conventions

- `*_core` — Core entity tables
- `*_local_core` — Localized lookup tables
- `*_enum_local2_core` — Enum lookup tables
- `*_cf_core` — Custom field tables

---

## 8. MDL File Schema (per file)

```json
{
  "catalog": "csod_dE",
  "schema": "dbo",
  "models": [{
    "name": "table_name",
    "tableReference": { "catalog": "...", "schema": "...", "table": "..." },
    "primaryKey": "pk_column",
    "columns": [{
      "name": "column_name",
      "type": "datetime|int|nvarchar|uniqueidentifier|...",
      "notNull": true|false,
      "properties": {
        "description": "...",
        "displayName": "...",
        "synonyms": "...",
        "businessMeaning": "...",
        "isPII": "True|False",
        "isSensitive": "True|False"
      }
    }]
  }]
}
```

---

## 9. Quick Reference: Category → Tables

| Category | Key Tables |
|----------|------------|
| Training completion | transcript_core, training_assignment_core, training_assignment_user_core |
| Compliance training | transcript_core, training_assignment_core, training_requirement_tag_core |
| Overdue tracking | transcript_core, training_assignment_core, transcript_status_local_core |
| Certification tracking | assessment_result_core, transcript_core, curriculum_structure_core |
| Training ROI | training_purchase_core, training_ilt_session_core, training_part_attendance_core |
| ILT utilization | training_ilt_session_core, training_part_attendance_core, instructor_core |
| Learning effectiveness | transcript_core, scorm_session, course_rating_core, assessment_result_core |
| User context | users_core, user_ou_core, ou_core, ou_hierarchy_core |
