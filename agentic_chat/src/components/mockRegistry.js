// mockRegistry.js
// Centralized registry for HR Compliance Strategy Map

export const REGISTRY = {
  sources: [
    { id: "src.training_assignments", label: "Training Assignments", icon: "db" },
    { id: "src.transcripts", label: "Transcripts", icon: "db" },
    { id: "src.users", label: "Users", icon: "db" },
    { id: "src.courses", label: "Courses", icon: "db" },
    { id: "src.certifications", label: "Certifications", icon: "db" },
  ],

  entities: [
    { id: "ent.employee", label: "Employee" },
    { id: "ent.training_assignment", label: "Training Assignment" },
    { id: "ent.course", label: "Course / Learning Object" },
    { id: "ent.certification", label: "Certification" },
    { id: "ent.ou", label: "Org Units (Dept / Location / Role)" },
  ],

  categories: [
    {
      id: "cat.identity",
      label: "Identity & Scoping",
      features: [
        {
          id: "feat.csod_user_id",
          label: "csod_user_id",
          type: "string",
          question: "What is the unique user ID for this employee in Cornerstone?",
          description: "Unique Cornerstone user identifier for the employee.",
          derivedFrom: ["users.user_id"],
        },
        {
          id: "feat.employee_department_ou",
          label: "employee_department_ou",
          type: "string",
          question: "What department does this employee belong to?",
          description: "Department OU for the employee.",
          derivedFrom: ["users.department_ou"],
        },
        {
          id: "feat.employee_location_ou",
          label: "employee_location_ou",
          type: "string",
          question: "What location or office does this employee work at?",
          description: "Location OU for the employee.",
          derivedFrom: ["users.location_ou"],
        },
      ],
    },
    {
      id: "cat.status",
      label: "Status & Deadlines",
      features: [
        {
          id: "feat.is_completed",
          label: "is_completed",
          type: "boolean",
          question: "Has the employee completed this training?",
          description: "True if the training status indicates completion.",
          derivedFrom: ["training_status_raw"],
        },
        {
          id: "feat.due_date",
          label: "due_date",
          type: "date",
          question: "When is this training due to be completed?",
          description: "Training due date / deadline date.",
          derivedFrom: ["training_assignments.due_at", "transcripts.due_at"],
        },
        {
          id: "feat.is_overdue",
          label: "is_overdue",
          type: "boolean",
          question: "Is this training past its due date and not yet completed?",
          description: "True when due_date is in the past AND is_completed is false.",
          derivedFrom: ["due_date", "is_completed"],
        },
        {
          id: "feat.days_overdue",
          label: "days_overdue",
          type: "int",
          question: "How many days overdue is this training?",
          description: "If overdue, number of days past due_date; else 0.",
          derivedFrom: ["due_date", "is_completed"],
        },
        {
          id: "feat.completed_on_time",
          label: "completed_on_time",
          type: "boolean",
          question: "Was this training completed on or before the due date?",
          description: "True when completed_date is on/before due_date.",
          derivedFrom: ["completed_date", "due_date", "is_completed"],
        },
      ],
    },
    {
      id: "cat.progress",
      label: "Progress & Engagement",
      features: [
        {
          id: "feat.progress_percent",
          label: "progress_percent",
          type: "float",
          question: "What percentage of the training has the employee completed?",
          description: "Current training progress percentage (0–100).",
          derivedFrom: ["training_assignments.progress_percent", "transcripts.progress_percent"],
        },
        {
          id: "feat.days_since_last_activity",
          label: "days_since_last_activity",
          type: "int",
          question: "How many days since the employee last accessed this training?",
          description: "Days since last activity timestamp.",
          derivedFrom: ["last_activity_ts"],
        },
        {
          id: "feat.engagement_stale_flag",
          label: "engagement_stale_flag",
          type: "boolean",
          question: "Has the employee been inactive on this training for too long?",
          description: "True if days_since_last_activity exceeds a threshold.",
          derivedFrom: ["days_since_last_activity"],
        },
      ],
    },
    {
      id: "cat.cert",
      label: "Certification Expiry",
      features: [
        {
          id: "feat.is_certification_expired",
          label: "is_certification_expired",
          type: "boolean",
          question: "Has this certification already expired?",
          description: "True if certification_expiration_date is in the past.",
          derivedFrom: ["certification_expiration_date"],
        },
        {
          id: "feat.days_until_certification_expiry",
          label: "days_until_certification_expiry",
          type: "int",
          question: "How many days until this certification expires?",
          description: "Days until certification expiration.",
          derivedFrom: ["certification_expiration_date"],
        },
      ],
    },
    {
      id: "cat.ml",
      label: "ML Predictions (Optional)",
      features: [
        {
          id: "feat.predicted_completion_probability_by_due_date",
          label: "predicted_completion_probability_by_due_date",
          type: "float",
          modelBased: true,
          question:
            "What is the predicted probability that this employee will complete the training by the due date?",
          description:
            "Model-estimated probability that the assignment will be completed on/before due_date.",
          derivedFrom: [
            "progress_percent",
            "days_until_due",
            "days_since_last_activity",
            "course_type",
            "estimated_duration_minutes",
            "employee_department_ou",
            "employee_role",
          ],
        },
      ],
    },
  ],

  metrics: [
    {
      id: "met.compliance_gap_count",
      label: "compliance_gap_count",
      type: "COUNT",
      metricType: "COUNT", // alias for HRComplianceStrategy compatibility
      dashboard: "Compliance Gap",
      dashboardSection: "Compliance Gap", // alias for HRComplianceStrategy compatibility
      question: "How many employees are missing required training?",
      description: "Count of employees missing required training or certifications",
      required_entities: ["Employee", "Training", "Certification"],
      aggregation_levels: ["Department", "Location OU", "Role"],
      feature_patterns: ["compliance_gap"],
      schemas: ["employee", "training_instances", "certifications"],
      dependsOnFeatures: [
        "feat.is_overdue",
        "feat.days_overdue",
        "feat.is_completed",
        "feat.is_certification_expired",
        "feat.days_until_certification_expiry",
        "feat.employee_department_ou",
      ],
    },
    {
      id: "met.training_completion_rate",
      label: "training_completion_rate",
      type: "PERCENTAGE",
      metricType: "PERCENTAGE", // alias for HRComplianceStrategy compatibility
      dashboard: "Compliance Rate",
      dashboardSection: "Compliance Rate", // alias for HRComplianceStrategy compatibility
      question: "What is the training completion rate?",
      description: "Percentage of employees who completed training within the deadline",
      required_entities: ["Employee", "Training"],
      aggregation_levels: ["Department", "Location OU", "Course", "Training"],
      feature_patterns: ["training_completion"],
      schemas: ["training_instances", "employee"],
      dependsOnFeatures: [
        "feat.is_completed",
        "feat.completed_on_time",
        "feat.due_date",
        "feat.employee_department_ou",
      ],
    },
    {
      id: "met.forecasted_compliance_rate",
      label: "forecasted_compliance_rate",
      type: "FORECAST",
      metricType: "FORECAST", // alias for HRComplianceStrategy compatibility
      dashboard: "Compliance Rate",
      dashboardSection: "Compliance Rate", // alias for HRComplianceStrategy compatibility
      question: "What is the forecasted compliance rate?",
      description:
        "Forecasted compliance rate looking ahead (quarterly) based on current registrations due in the future",
      required_entities: ["Employee", "Course", "Training"],
      aggregation_levels: ["Location OU", "Department OU", "Quarter", "Year"],
      feature_patterns: ["training_completion"],
      schemas: ["training_instances", "employee", "course"],
      dependsOnFeatures: [
        "feat.is_completed",
        "feat.due_date",
        "feat.progress_percent",
        "feat.predicted_completion_probability_by_due_date",
      ],
    },
  ],
};

// Flat features array (for HRComplianceStrategy.jsx compatibility)
// Generated from categories
export const FEATURES_FLAT = REGISTRY.categories.flatMap((cat) =>
  cat.features.map((f) => ({
    ...f,
    dataType: f.type?.toUpperCase() || "STRING", // alias: dataType for compatibility
    category: cat.label,
  }))
);

// Edge definitions for lineage
export const EDGE_DEFINITIONS = {
  sources_to_entities: {
    "src.training_assignments": ["ent.training_assignment"],
    "src.transcripts": ["ent.training_assignment"],
    "src.users": ["ent.employee", "ent.ou"],
    "src.courses": ["ent.course"],
    "src.certifications": ["ent.certification"],
  },
  entities_to_features: {
    "ent.employee": ["feat.csod_user_id", "feat.employee_department_ou", "feat.employee_location_ou"],
    "ent.training_assignment": [
      "feat.is_completed",
      "feat.due_date",
      "feat.is_overdue",
      "feat.days_overdue",
      "feat.completed_on_time",
      "feat.progress_percent",
      "feat.days_since_last_activity",
      "feat.engagement_stale_flag",
    ],
    "ent.certification": ["feat.is_certification_expired", "feat.days_until_certification_expiry"],
  },
  features_to_metrics: {
    "met.compliance_gap_count": [
      "feat.is_overdue",
      "feat.days_overdue",
      "feat.is_completed",
      "feat.is_certification_expired",
      "feat.days_until_certification_expiry",
      "feat.employee_department_ou",
    ],
    "met.training_completion_rate": ["feat.is_completed", "feat.completed_on_time", "feat.employee_department_ou"],
    "met.forecasted_compliance_rate": [
      "feat.is_completed",
      "feat.due_date",
      "feat.progress_percent",
      "feat.predicted_completion_probability_by_due_date",
    ],
  },
};

// Edges array (for HRComplianceStrategy.jsx compatibility)
// Generated from EDGE_DEFINITIONS - flat array of [source, target] pairs
export const EDGES = [
  // sources -> entities
  ...Object.entries(EDGE_DEFINITIONS.sources_to_entities).flatMap(([src, ents]) =>
    ents.map((ent) => [src, ent])
  ),
  // entities -> features
  ...Object.entries(EDGE_DEFINITIONS.entities_to_features).flatMap(([ent, feats]) =>
    feats.map((feat) => [ent, feat])
  ),
  // features -> metrics
  ...Object.entries(EDGE_DEFINITIONS.features_to_metrics).flatMap(([met, feats]) =>
    feats.map((feat) => [feat, met])
  ),
];

// Mock data preview rows
export const MOCK_PREVIEW_ROWS = [
  {
    employee_id: "E-1021",
    course: "HIPAA Basics",
    due_date: "2026-02-15",
    is_completed: false,
    is_overdue: true,
    days_overdue: 12,
    progress_percent: 40,
    department: "Sales",
    location: "NYC",
  },
  {
    employee_id: "E-1407",
    course: "Security Awareness",
    due_date: "2026-02-28",
    is_completed: false,
    is_overdue: false,
    days_overdue: 0,
    progress_percent: 10,
    department: "Engineering",
    location: "SFO",
  },
  {
    employee_id: "E-1188",
    course: "Code of Conduct",
    due_date: "2026-01-31",
    is_completed: true,
    is_overdue: false,
    days_overdue: 0,
    progress_percent: 100,
    department: "HR",
    location: "Remote",
  },
];

// Mock KPI helpers
export function mockKpiValue(nodeId) {
  if (nodeId === "met.compliance_gap_count") return "314";
  if (nodeId === "met.training_completion_rate") return "72.1%";
  if (nodeId === "met.forecasted_compliance_rate") return "68.5%";
  return "—";
}

export function mockKpiTarget(nodeId) {
  if (nodeId === "met.compliance_gap_count") return "≤ 100";
  if (nodeId === "met.training_completion_rate") return "≥ 95%";
  if (nodeId === "met.forecasted_compliance_rate") return "≥ 90%";
  return "—";
}

export function mockKpiScore(nodeId) {
  if (nodeId === "met.compliance_gap_count") return "Watch";
  if (nodeId === "met.training_completion_rate") return "OK";
  if (nodeId === "met.forecasted_compliance_rate") return "At Risk";
  return "—";
}

// Score color helper: returns CSS class or color based on score status
export function getScoreColor(score) {
  const s = String(score).toLowerCase();
  if (s === "ok" || s === "good" || s === "green") return "bg-green-500";
  if (s === "watch" || s === "warning" || s === "yellow") return "bg-yellow-500";
  if (s === "at risk" || s === "risk" || s === "red" || s === "bad") return "bg-red-500";
  return "bg-zinc-500";
}

// Get objective-level score (aggregate of KPIs)
export function getObjectiveScore(kpis) {
  if (!kpis || kpis.length === 0) return { score: "—", color: "bg-zinc-500" };
  
  const scores = kpis.map((kpi) => mockKpiScore(kpi.nodeId).toLowerCase());
  
  // If any KPI is "at risk", objective is at risk
  if (scores.some((s) => s === "at risk" || s === "risk" || s === "red")) {
    return { score: "At Risk", color: "bg-red-500" };
  }
  // If any KPI is "watch", objective is watch
  if (scores.some((s) => s === "watch" || s === "warning" || s === "yellow")) {
    return { score: "Watch", color: "bg-yellow-500" };
  }
  // All OK
  return { score: "OK", color: "bg-green-500" };
}

// Helper: Get type badge string
export function typeBadge(type) {
  const map = {
    boolean: "BOOLEAN",
    string: "STRING",
    int: "INT",
    float: "FLOAT",
    date: "DATE",
    timestamp: "TIMESTAMP",
  };
  return map[type] ?? String(type).toUpperCase();
}
