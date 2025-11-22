# Table Usage Matrix - Visual Summary
## Quick Reference for Database Tables by Use Case

---

## 📊 Table Usage Frequency Chart

### Tier 1: Core Tables (Used in 90%+ of Use Cases)
```
transcript_core              ████████████████████ 20/20 (100%)
training_core                ███████████████████  19/20 (95%)
users_core                   ██████████████████   18/20 (90%)
```

### Tier 2: Frequently Used Tables (Used in 50-90% of Use Cases)
```
transcript_assignment_core   ███████████████      15/20 (75%)
user_ou_core                 ████████             8/20 (40%)
ou_core                      ████████             8/20 (40%)
training_type_core           ███████              7/20 (35%)
```

### Tier 3: Supporting Tables (Used in 20-50% of Use Cases)
```
user_status_core             █████                5/20 (25%)
training_requirement_tag     █████                5/20 (25%)
user_login_core              ███                  3/20 (15%)
address_core                 █                    1/20 (5%)
session_core                 ██                   2/20 (10%)
UserRating                   ██                   2/20 (10%)
```

### Tier 4: Specialized Tables (Used in <20% of Use Cases)
```
UserSkillMap / UserSkills    █                    1/20 (5%)
training_delivery_method     █                    1/20 (5%)
skill_training_map           █                    1/20 (5%)
curriculum_core              █                    1/20 (5%)
```

---

## 🗺️ Use Case × Table Matrix

| Use Case | Core 4 | Org | Rating | Skills | Special |
|----------|--------|-----|--------|--------|---------|
| **TREND ANALYSIS** |
| 1. Enrollment Trends | ✓✓✓✓ | ✓✓ | | | |
| 6. Response Time | ✓✓✓✓ | ✓✓ | | | |
| 11. Content Impact | ✓✓✓ | | ✓ | | |
| 16. Instructor Trends | ✓✓✓ | | ✓ | | Session |
| **RISK SCORING** |
| 2. Non-Completion | ✓✓✓✓ | | | | Status |
| 7. Dept Compliance | ✓✓✓✓ | ✓✓ | | | Req Tag |
| 12. Cert Expiration | ✓✓✓ | | | | Login |
| 17. Mandatory Compliance | ✓✓✓✓ | ✓✓ | | | Req Tag |
| **ANOMALY DETECTION** |
| 3. Completion Patterns | ✓✓ | | | | |
| 8. Enrollment Spikes | ✓✓✓ | | | | |
| 13. Path Deviation | ✓✓✓ | | | | Curriculum |
| 18. Scoring Patterns | ✓✓ | | | | Session |
| **SEGMENTATION** |
| 4. Learner Personas | ✓✓✓ | | | | Login |
| 9. Course Difficulty | ✓✓ | | | | |
| 14. Geographic Perf | ✓✓✓ | | | | Address |
| 19. Learning Style | ✓✓✓ | | | | Delivery |
| **FORECASTING** |
| 5. Completion Volume | ✓✓ | | | | |
| 10. Learner Capacity | ✓✓ | | | | Login |
| 15. Training Budget | ✓✓ | | | | Cost |
| 20. Skill Gap Timeline | ✓✓✓✓ | | | ✓ | Skill Map |

**Legend:**
- Core 4 = transcript_core, training_core, users_core, transcript_assignment_core
- Org = user_ou_core, ou_core
- Rating = UserRating table
- Skills = UserSkillMap, UserSkills
- Special = Other specialized tables

---

## 🔗 Primary Join Paths

### Path 1: User → Assignments → Completions
```
users_core
    ↓ (user_id)
transcript_assignment_core
    ↓ (assignment_id)
transcript_core
    ↓ (training_id)
training_core
```
**Used in:** 75% of use cases
**Purpose:** Track learner progress through assigned training

### Path 2: User → Department → Assignments
```
users_core
    ↓ (user_id)
user_ou_core
    ↓ (ou_id)
ou_core
    ↓
transcript_assignment_core (via user_id)
```
**Used in:** 40% of use cases
**Purpose:** Organizational/departmental analysis

### Path 3: User → Geography → Performance
```
users_core
    ↓ (address_id)
address_core
    ↓
transcript_core (via user_id)
```
**Used in:** 5% of use cases (but critical for regional analysis)
**Purpose:** Geographic performance analysis

### Path 4: Training → Sessions → Ratings
```
training_core
    ↓ (training_id)
session_core
    ↓ (session_id)
transcript_core
    ↓ (user_id, session_id)
UserRating
```
**Used in:** 10% of use cases
**Purpose:** Instructor effectiveness and satisfaction analysis

### Path 5: User → Skills → Training Gap
```
users_core
    ↓ (user_id)
UserSkillMap
    ↓ (skill_id)
skill_training_map
    ↓ (training_id)
training_core
```
**Used in:** 5% of use cases
**Purpose:** Skill gap analysis and workforce planning

---

## 📋 Use Case Implementation Checklist

### For Each Use Case, Verify:

#### ✅ Basic Requirements
- [ ] Core tables accessible (transcript_core, training_core, users_core)
- [ ] Date fields populated (assigned_dt, completed_dt)
- [ ] Status fields properly coded
- [ ] Foreign key relationships validated

#### ✅ Data Quality
- [ ] Sufficient historical data (minimum 12 months recommended)
- [ ] No major gaps in date sequences
- [ ] Null handling strategy defined
- [ ] Sample size adequate for analysis (n ≥ 20-30 per group)

#### ✅ Performance Optimization
- [ ] Indexes on join columns (user_id, training_id, etc.)
- [ ] Indexes on date columns for filtering
- [ ] Consider date partitioning for large tables
- [ ] Pre-aggregate common metrics if needed

#### ✅ Custom Fields/Tables
- [ ] Identify any missing required fields
- [ ] Plan creation of custom tables if needed
- [ ] Document business logic for derived fields
- [ ] Validate custom field definitions with stakeholders

---

## 🎯 Use Case Selection Guide

### Start Here (Minimal Data Requirements)
**Best for Initial Implementation:**

1. **Use Case 3: Unusual Completion Patterns**
   - Tables: transcript_core, training_core
   - Complexity: Low
   - Value: Quick wins identifying data quality issues

2. **Use Case 5: Completion Volume Forecasting**
   - Tables: transcript_core, training_core
   - Complexity: Medium
   - Value: Capacity planning

3. **Use Case 9: Course Difficulty Clustering**
   - Tables: transcript_core, training_core
   - Complexity: Medium
   - Value: Better course catalog organization

### Medium Complexity (Standard Data Model)
**Good Second Phase Implementation:**

4. **Use Case 1: Enrollment Trends by Department**
   - Tables: +user_ou_core, ou_core
   - Complexity: Medium
   - Value: Identify engagement patterns

5. **Use Case 2: Non-Completion Risk**
   - Tables: All Core 4
   - Complexity: Medium-High
   - Value: Proactive intervention

6. **Use Case 4: Learner Personas**
   - Tables: Core 3 + user_login_core
   - Complexity: Medium
   - Value: Personalization strategy

### Advanced (Custom Data Required)
**Requires Additional Setup:**

7. **Use Case 16: Instructor Effectiveness**
   - Tables: +session_core, UserRating
   - Custom: Session-instructor mapping
   - Complexity: High
   - Value: Teaching quality improvement

8. **Use Case 20: Skill Gap Timeline**
   - Tables: +UserSkillMap, skill_training_map
   - Custom: Skill framework, training mappings
   - Complexity: High
   - Value: Strategic workforce planning

---

## 🔍 Quick Lookup: "I Have These Tables, What Can I Do?"

### Scenario 1: Core 4 Tables Only
**Available Use Cases:** 2, 3, 5, 8, 9
**Best Starting Point:** Use Case 3 (Anomaly Detection) or 5 (Forecasting)

### Scenario 2: Core 4 + Organizational Tables
**Available Use Cases:** 1, 2, 6, 7, 8, 17
**Best Starting Point:** Use Case 1 (Enrollment Trends) or 7 (Compliance Risk)

### Scenario 3: Core 4 + Address Tables
**Available Use Cases:** 14 (Geographic Clustering)
**Best Starting Point:** Use Case 14 for regional insights

### Scenario 4: Core 4 + Session/Rating Tables
**Available Use Cases:** 11, 16, 18
**Best Starting Point:** Use Case 11 (Content Impact) or 16 (Instructor Effectiveness)

### Scenario 5: Core 4 + Skills Tables
**Available Use Cases:** 20 (Skill Gap Timeline)
**Best Starting Point:** Use Case 20 for workforce planning

### Scenario 6: Full Data Model
**Available Use Cases:** All 20
**Best Starting Point:** Use Case 2 (Risk Scoring) or 4 (Segmentation)

---

## 📐 Table Relationship Diagram (ASCII)

```
                    ┌─────────────────┐
                    │   users_core    │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ address_core │  │ user_ou_core │  │user_login_core│
    └──────────────┘  └──────┬───────┘  └──────────────┘
                             │
                             ▼
                      ┌─────────────┐
                      │  ou_core    │
                      └─────────────┘

    ┌──────────────────────────────────────────────┐
    │                                              │
    │  USER ENROLLMENT & COMPLETION CORE FLOW      │
    │                                              │
    └──────────────────────────────────────────────┘

            users_core
                 │
                 ▼
    transcript_assignment_core ◄──────┐
                 │                     │
                 │                     │ (training_id)
                 ▼                     │
         transcript_core              │
                 │                     │
                 │                     │
                 ▼                     │
         ┌──────────────┐             │
         │training_core │─────────────┘
         └──────┬───────┘
                │
                ├─────► training_type_core
                │
                ├─────► training_requirement_tag_core
                │
                └─────► training_delivery_method_local_core


    ┌──────────────────────────────────────────────┐
    │                                              │
    │  OPTIONAL ENRICHMENT TABLES                  │
    │                                              │
    └──────────────────────────────────────────────┘

    training_core ──► session_core ──► UserRating
                            │
                            └──► instructor (users_core)

    users_core ──► UserSkillMap ──► UserSkills
                        │
                        └──► skill_training_map ──► training_core
```

---

## 💡 Pro Tips for Implementation

### 1. **Start with Data Profiling**
Before implementing any use case:
- Count distinct values in key fields
- Check NULL percentages
- Validate date ranges
- Verify foreign key integrity

### 2. **Build Progressive Complexity**
```
Phase 1: Simple aggregations (Use Cases 3, 5, 9)
    ↓
Phase 2: Trend analysis (Use Cases 1, 6, 11)
    ↓
Phase 3: Predictive models (Use Cases 2, 7, 12)
    ↓
Phase 4: Advanced analytics (Use Cases 4, 14, 19, 20)
```

### 3. **Create Reusable Components**
Common patterns to build once:
- Active learner definition
- Completion rate calculation
- Overdue assignment logic
- Time-to-completion metric
- Engagement score formula

### 4. **Performance Optimization Priorities**
1. Index foreign keys (user_id, training_id)
2. Index date fields (assigned_dt, completed_dt)
3. Consider materialized views for common aggregations
4. Partition large tables by date
5. Archive old data if performance issues persist

### 5. **Data Quality Monitoring**
Set up alerts for:
- Missing required fields
- Anomalous date values (future dates, negative durations)
- Orphaned records (FKs with no matching PK)
- Sudden drops in data volume
- Unusual NULL percentages

---

## 📞 Support Tables Reference

### Status/Lookup Tables
| Table | Purpose | Key Field |
|-------|---------|-----------|
| user_status_core | User employment status | user_status_id |
| transcript_status_local_core | Training completion status | status_code |
| training_type_core | Course categories | training_type_id |
| training_delivery_method_local_core | How training is delivered | delivery_method_id |
| ou_type_core | Organization unit types | ou_type_id |
| user_termination_reason_core | Why users left | termination_reason_id |
| training_requirement_tag_core | Mandatory vs optional | requirement_tag_id |

### Custom Fields Often Needed
| Field | Table | Purpose | Use Cases |
|-------|-------|---------|-----------|
| modified_dt | training_core | Track content updates | 11 |
| is_certification | training_core | Flag certifications | 12 |
| cost_per_completion | training_cost | Budget planning | 15 |
| instructor_user_id | session_core | Link instructors | 16 |
| sequence_number | training_core | Learning paths | 13 |
| expiration_dt | transcript_core | Certification tracking | 12 |

---

## ✨ Summary

**Most Critical Tables:**
1. transcript_core (the heart of all analysis)
2. training_core (what was trained)
3. users_core (who was trained)
4. transcript_assignment_core (when assigned)

**Most Common Join:**
```sql
FROM users_core u
JOIN transcript_assignment_core ta ON u.user_id = ta.user_id
LEFT JOIN transcript_core t ON ta.assignment_id = t.transcript_id
JOIN training_core tr ON ta.training_id = tr.training_id
```

**Quick Implementation Path:**
Start with 2-3 tables → Add organizational context → Add enrichment tables → Build custom fields

This visual summary provides a rapid reference for understanding table requirements across all 20 analytical use cases.
