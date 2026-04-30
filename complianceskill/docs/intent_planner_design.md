## Design Doc: Direct Analysis Query Planner + Causal Decomposition

### Goal

Add a new planning step in the **Direct answer** flow before `generate_single_preview`. Today, Direct flow auto-confirms planner intents and short-circuits into a single preview response, while Explore flow runs the heavier `csod-workflow` with causal graph, metric retrieval, cross-concept checks, and metric selection.  

The new step should decide:

1. Is this really a single direct question?
2. Does it contain multiple embedded questions?
3. Does it require RCA / causal reasoning?
4. Should the system rewrite it into multiple analysis questions?
5. Can Direct answer still return one synthesized preview, or should it recommend Explore?

---

# 1. Updated Direct Flow

```text
User question
  ↓
Mode selected = Direct answer
  ↓
intent_splitter
  ↓
mdl_intent_resolver
  ↓
NEW: direct_query_decomposition_planner
  ↓
IF simple_single_question:
    generate_single_preview()
ELSE IF multi_question_but_direct_answerable:
    generate_multi_question_preview()
ELSE IF causal_rca_required:
    causal_query_planner + causal_edge_retrieval
    generate_rca_preview()
ELSE IF too broad / needs metric exploration:
    return “Explore recommended” with suggested questions
```

This preserves Direct’s lightweight behavior, but prevents the system from answering complex questions as if they are simple one-chart questions.

---

# 2. New Node: `direct_query_decomposition_planner`

### Purpose

Classify the user question into one of these planning modes:

```json
{
  "planning_mode": "single_direct | multi_question | causal_rca | compare_segments | explore_recommended",
  "needs_causal_edges": true,
  "needs_multiple_questions": true,
  "confidence": 0.0,
  "reason": "...",
  "atomic_questions": [],
  "primary_metric_candidates": [],
  "supporting_metric_candidates": [],
  "required_tables": [],
  "causal_focus": {
    "effect_metric": null,
    "candidate_drivers": [],
    "confounders": [],
    "lag_windows_days": []
  }
}
```

---

# 3. When to Trigger Multi-Question Planning

Trigger when the user asks:

### Multiple questions in one sentence

Example:

> Why did compliance drop in Q4, which departments caused it, and are overdue assignments increasing?

Rewrite into:

```json
[
  {
    "question_id": "q1",
    "question": "Did compliance rate drop in Q4 compared with the prior period?",
    "analysis_type": "trend_detection"
  },
  {
    "question_id": "q2",
    "question": "Which departments contributed most to the compliance drop?",
    "analysis_type": "segment_contribution"
  },
  {
    "question_id": "q3",
    "question": "Did overdue assignment counts increase before or during the compliance drop?",
    "analysis_type": "causal_driver_check"
  }
]
```

### RCA / alert analysis

Example:

> Compliance rate alert fired for Sales. Why did this happen?

Rewrite into:

```json
[
  {
    "question": "Did compliance rate decline for Sales during the alert window?",
    "metric": "compliance_rate"
  },
  {
    "question": "Did missed deadlines increase before the compliance decline?",
    "metric": "missed_deadline_count"
  },
  {
    "question": "Did overdue trainings increase before missed deadlines?",
    "metric": "overdue_count"
  },
  {
    "question": "Is the issue explained by cohort size or assignment volume?",
    "metric": "learner_total / assigned_training_count"
  }
]
```

This aligns well with your causal seed, where missed deadlines directly reduce compliance rate, completion rate reduces missed deadlines, overdue count can affect completion behavior, and learner count is a confounder for absolute overdue/missed-deadline counts.   

---

# 4. Tables to Use

For LMS compliance RCA, start with:

```json
{
  "primary_tables": [
    "transcript_core",
    "training_assignment_core",
    "training_assignment_user_core"
  ],
  "supporting_tables": [
    "users_core",
    "ou_core",
    "user_ou_core",
    "transcript_status_local_core",
    "training_requirement_tag_core"
  ],
  "optional_tables": [
    "assessment_result_core",
    "training_ilt_session_core",
    "training_part_attendance_core"
  ]
}
```

These match the MDL reference: transcript/status tables support completion, overdue, and compliance dashboards; assignment tables support assigned-vs-completed and overdue assignment analysis.  

---

# 5. Prompt: Direct Query Decomposition Planner

```text
You are the Direct Analysis Query Planner for an LMS analytics agent.

Your job is to inspect the user question and decide whether it can be answered as:
1. a single direct analysis,
2. multiple smaller analysis questions,
3. a causal/root-cause analysis,
4. a segment comparison,
5. or whether the user should be moved to Explore mode.

Use the available MDL metadata, metric registry, and causal edge registry.

Instructions:
- Do not answer the question.
- Do not generate SQL.
- Decompose only when necessary.
- Preserve the user’s business intent.
- Prefer 2–5 atomic questions.
- For RCA questions, identify the effect metric, likely driver metrics, confounders, and lag windows.
- For alert RCA, always include:
  1. Validate alert movement.
  2. Identify segment contribution.
  3. Check proximate causal drivers.
  4. Check confounders.
  5. Summarize likely explanation.
- If the question is too broad for Direct mode, set planning_mode = "explore_recommended".

Return strict JSON only.
```

---

# 6. Output Schema

```json
{
  "planning_mode": "causal_rca",
  "needs_causal_edges": true,
  "needs_multiple_questions": true,
  "direct_answer_allowed": true,
  "explore_recommended": false,
  "atomic_questions": [
    {
      "question_id": "q1",
      "question": "Did compliance rate decline for the selected cohort?",
      "analysis_type": "metric_delta",
      "target_metric": "compliance_rate",
      "tables": ["transcript_core", "training_assignment_core"]
    },
    {
      "question_id": "q2",
      "question": "Did missed deadlines increase before the compliance decline?",
      "analysis_type": "causal_driver_check",
      "target_metric": "missed_deadline_count",
      "tables": ["transcript_core", "training_assignment_core"]
    }
  ],
  "causal_focus": {
    "effect_metric": "compliance_rate",
    "candidate_drivers": [
      "missed_deadline_count",
      "completion_rate",
      "overdue_count",
      "assigned_training_count"
    ],
    "confounders": [
      "learner_total",
      "department_size",
      "assignment_volume"
    ],
    "lag_windows_days": [0, 7, 14, 21, 30]
  },
  "synthesis_instruction": "Answer as a concise RCA summary with likely driver, supporting evidence, and caveats."
}
```

---

# 7. Examples

### Example A: Simple Direct

User:

> Show overdue training trend for last quarter.

Output:

```json
{
  "planning_mode": "single_direct",
  "needs_causal_edges": false,
  "needs_multiple_questions": false,
  "direct_answer_allowed": true,
  "atomic_questions": [
    {
      "question": "Show overdue training trend for last quarter.",
      "analysis_type": "trend",
      "target_metric": "overdue_count",
      "tables": ["transcript_core", "training_assignment_core"]
    }
  ]
}
```

---

### Example B: Multiple Questions

User:

> Why is compliance down, which teams are affected, and what should we fix first?

Output:

```json
{
  "planning_mode": "multi_question",
  "needs_causal_edges": true,
  "needs_multiple_questions": true,
  "atomic_questions": [
    {
      "question": "Did compliance rate decline over the selected period?",
      "analysis_type": "metric_delta",
      "target_metric": "compliance_rate"
    },
    {
      "question": "Which teams contributed most to the compliance decline?",
      "analysis_type": "segment_contribution",
      "target_metric": "compliance_rate",
      "dimensions": ["department", "ou"]
    },
    {
      "question": "Which proximate drivers explain the decline?",
      "analysis_type": "causal_driver_check",
      "target_metric": "missed_deadline_count"
    },
    {
      "question": "Which fix has the highest likely impact?",
      "analysis_type": "recommendation_prioritization"
    }
  ]
}
```

---

### Example C: Alert RCA

User:

> Alert: compliance dropped 12% for nurses in Region West. What caused it?

Output:

```json
{
  "planning_mode": "causal_rca",
  "needs_causal_edges": true,
  "needs_multiple_questions": true,
  "atomic_questions": [
    {
      "question": "Validate whether compliance rate dropped 12% for nurses in Region West.",
      "analysis_type": "alert_validation",
      "target_metric": "compliance_rate"
    },
    {
      "question": "Check whether missed deadline count increased before the compliance drop.",
      "analysis_type": "causal_driver_check",
      "target_metric": "missed_deadline_count"
    },
    {
      "question": "Check whether overdue trainings increased before missed deadlines.",
      "analysis_type": "causal_driver_check",
      "target_metric": "overdue_count"
    },
    {
      "question": "Check whether assignment volume or learner count explains the change.",
      "analysis_type": "confounder_check",
      "target_metric": "learner_total"
    }
  ],
  "causal_focus": {
    "effect_metric": "compliance_rate",
    "candidate_drivers": [
      "missed_deadline_count",
      "overdue_count",
      "completion_rate"
    ],
    "confounders": [
      "learner_total",
      "assignment_volume"
    ]
  }
}
```

---

# 8. Implementation Instructions

Add this node after `mdl_intent_resolver` and before the direct short-circuit:

```python
workflow.add_node(
    "direct_query_decomposition_planner",
    direct_query_decomposition_planner_node
)
```

Direct flow should become:

```text
intent_splitter
→ mdl_intent_resolver
→ direct_query_decomposition_planner
→ area_matcher
→ area_confirm
→ metric_narration
→ direct_preview_router
```

Router behavior:

```python
if planning_mode == "single_direct":
    return generate_single_preview(...)

if planning_mode in ["multi_question", "compare_segments"]:
    return generate_multi_question_preview(...)

if planning_mode == "causal_rca":
    return retrieve_causal_edges(...)
           → generate_rca_preview(...)

if planning_mode == "explore_recommended":
    return render_explore_recommendation(...)
```

---

# 9. Direct Preview Synthesis Prompt

```text
You are generating a Direct Analysis answer.

You may receive one or more atomic analysis questions. Synthesize them into one concise business-facing response.

Instructions:
- Start with the direct answer.
- Then explain the supporting evidence.
- For RCA, separate:
  1. observed symptom,
  2. likely driver,
  3. supporting signals,
  4. confounders checked,
  5. recommended next action.
- Do not overstate causality.
- Use “likely driver” unless causal evidence is confirmed.
- If using causal edges, mention direction and lag only when helpful.
- Keep the response suitable for an inline preview card.
```

---

# 10. Recommended Preview Card Structure

```json
{
  "title": "Compliance Drop RCA",
  "summary": "Compliance appears to have dropped primarily because missed deadlines increased in the same cohort.",
  "sections": [
    {
      "label": "Observed Alert",
      "content": "Compliance rate declined 12% for nurses in Region West."
    },
    {
      "label": "Likely Driver",
      "content": "Missed deadline count increased before the compliance drop."
    },
    {
      "label": "Supporting Signals",
      "content": "Overdue trainings and assignment volume also increased."
    },
    {
      "label": "Confounders",
      "content": "Normalize by learner count and assignment volume before comparing departments."
    },
    {
      "label": "Recommended Action",
      "content": "Prioritize overdue mandatory training assignments in the affected cohort."
    }
  ]
}
```

---

## Bottom Line

Add a lightweight **Direct Query Decomposition Planner** so Direct mode can still feel fast, but intelligently handles RCA, alert analysis, and compound questions. It should not run the full Explore workflow, but it should borrow the same causal graph concepts already used in `csod-workflow`.
