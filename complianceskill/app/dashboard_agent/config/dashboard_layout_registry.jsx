import { useState, useCallback } from "react";

// ═══════════════════════════════════════════════════════════════════
// CCE DYNAMIC DASHBOARD LAYOUT REGISTRY & DESIGN STRATEGY
// ═══════════════════════════════════════════════════════════════════
// Extracted from: demo1_alert_intelligence.html + demo2_soc2_monitoring.html
// Purpose: Composable layout primitives for generating dashboards
// across Security, Cornerstone LMS, Workday HR, and hybrid domains
// ═══════════════════════════════════════════════════════════════════

// ── DESIGN SYSTEM TOKENS ──────────────────────────────────────────
const THEMES = {
  light: {
    id: "light", name: "Editorial Light (SOC2 Monitoring)",
    origin: "demo2_soc2_monitoring.html",
    vars: {
      bg: "#faf9f7", bg2: "#f4f2ee", bg3: "#edeae4",
      surf: "#ffffff", surf2: "#f7f5f1",
      ink: "#1c1917", ink2: "#44403c", ink3: "#78716c",
      rule: "#e7e3dd", rule2: "#d6d0c8",
      accent: "#c2400c", accent2: "#ea580c",
      blue: "#1e40af", blue2: "#2563eb",
      green: "#166534", green2: "#16a34a",
      amber: "#92400e", amber2: "#d97706",
      red: "#991b1b", red2: "#dc2626",
      purple: "#6b21a8",
    },
    fonts: { display: "Fraunces, serif", mono: "DM Mono, monospace", sans: "Nunito, sans-serif" },
    useCases: ["Compliance monitoring", "Audit dashboards", "Executive posture views", "Workday HR overview"]
  },
  dark: {
    id: "dark", name: "Command Dark (Alert Intelligence)",
    origin: "demo1_alert_intelligence.html",
    vars: {
      bg: "#05080f", bg2: "#0a0f1e", bg3: "#0f1627",
      surf: "#131d30", surf2: "#192540",
      ink: "#b8cae0", ink2: "#6a82a8", ink3: "#3a4e6a",
      rule: "#1e2d47", rule2: "#253558",
      accent: "#3b82f6", accent2: "#60a5fa",
      blue: "#3b82f6", blue2: "#60a5fa",
      green: "#22c55e", green2: "#22c55e",
      amber: "#f97316", amber2: "#f97316",
      red: "#ef4444", red2: "#ef4444",
      purple: "#a855f7",
    },
    fonts: { display: "Syne, sans-serif", mono: "IBM Plex Mono, monospace", sans: "Syne, sans-serif" },
    useCases: ["SOC operations", "Alert triage", "Real-time monitoring", "Incident response"]
  }
};

// ── LAYOUT PRIMITIVES (extracted from both dashboards) ────────────
const LAYOUT_PRIMITIVES = {
  topbar: {
    id: "topbar",
    name: "Topbar",
    category: "chrome",
    description: "Application header with brand, context label, and utility controls (API key, connection status, live indicator)",
    extracted_from: ["demo1", "demo2"],
    css_pattern: "height:54px; display:flex; align-items:center; gap:1rem; padding:0 1.25rem",
    slots: ["brand", "context_label", "live_indicator", "utility_controls"],
    variants: [
      { id: "topbar-light", theme: "light", bg: "var(--ink)", color: "#fff" },
      { id: "topbar-dark", theme: "dark", bg: "var(--bg2)", color: "#fff", border: "1px solid var(--b1)" }
    ]
  },
  posture_strip: {
    id: "posture_strip",
    name: "Posture Strip / KPI Bar",
    category: "summary",
    description: "Horizontal stat cards showing 4-8 headline KPIs. Each cell shows a big value + mono label. Values are color-coded by status (pass/warn/fail).",
    extracted_from: ["demo2"],
    css_pattern: "display:grid; grid-template-columns:repeat(N,1fr); border-bottom:2px solid var(--rule)",
    slots: ["stat_cells"],
    config: { min_cells: 3, max_cells: 8 },
    domain_examples: {
      security: ["Overall Posture", "CC Families", "Controls Degraded", "Controls Critical", "Evidence Complete", "Days to Audit"],
      cornerstone: ["Training Completion %", "Overdue Certs", "Active Learners", "Compliance Score", "Avg Course Rating", "Courses Published"],
      workday: ["Open Positions", "Time-to-Hire", "Turnover Rate", "Headcount", "Diversity Index", "Pending Approvals"],
      hybrid: ["Deprovisioning Lag", "HIPAA Cert Expiry", "SCIM Sync Health", "Access Reviews Due", "Training Compliance", "Risk Score"]
    }
  },
  three_panel: {
    id: "three_panel",
    name: "Three-Panel Command Layout",
    category: "scaffold",
    description: "Primary layout scaffold: Left list/navigation (340-380px) → Center detail/graph (flex) → Right chat/actions (320-340px). Each panel has a header + scrollable body.",
    extracted_from: ["demo1", "demo2"],
    css_pattern: "display:grid; grid-template-columns:380px 1fr 340px; flex:1; overflow:hidden",
    panels: [
      { slot: "navigation", width: "340-380px", role: "Master list — items to select/filter" },
      { slot: "detail", width: "1fr", role: "Detail view — expanded info for selected item" },
      { slot: "actions", width: "320-340px", role: "Contextual actions — chat, AI advisor, workflows" }
    ],
    panel_anatomy: {
      header: "panel-hdr: mono title + status badges + action buttons",
      body: "panel-body: scrollable content area",
      footer: "optional: input bar, suggestion chips"
    }
  },
  two_panel: {
    id: "two_panel",
    name: "Two-Panel Split",
    category: "scaffold",
    description: "Simplified layout for focused workflows. Left list → Right detail. No chat panel.",
    css_pattern: "display:grid; grid-template-columns:400px 1fr; flex:1; overflow:hidden",
    panels: [
      { slot: "navigation", width: "400px", role: "Master list" },
      { slot: "detail", width: "1fr", role: "Detail view" }
    ]
  },
  panel_with_tabs: {
    id: "panel_with_tabs",
    name: "Tabbed Panel",
    category: "scaffold",
    description: "Panel body with tab bar for switching views. Used in detail panels for signal/evidence/causal tabs.",
    extracted_from: ["demo2"],
    css_pattern: "tabs as flex row with border-bottom, tab-content toggled via display",
    slots: ["tab_bar", "tab_contents"]
  },
  filter_bar: {
    id: "filter_bar",
    name: "Filter Bar",
    category: "control",
    description: "Horizontal chip-style severity/status filters. Mono font, uppercase, color-coded active states.",
    extracted_from: ["demo1"],
    css_pattern: "display:flex; gap:.35rem; padding:.6rem .75rem; border-bottom:1px solid var(--b1)",
    config: { filters: ["All", "Critical", "High", "Medium", "Low"] },
    domain_examples: {
      security: ["All", "Critical", "High", "Medium", "Low"],
      cornerstone: ["All", "Overdue", "In Progress", "Completed", "Not Started"],
      workday: ["All", "Open", "In Review", "Approved", "Closed"],
      hybrid: ["All", "Failing", "Degraded", "Passing", "Not Evaluated"]
    }
  },
  list_card: {
    id: "list_card",
    name: "Selectable List Card",
    category: "component",
    description: "Clickable card in the navigation panel. Shows badge, title, subtitle, progress bar, status meta. Selected state adds left border accent + bg tint.",
    extracted_from: ["demo1", "demo2"],
    anatomy: {
      row1: "badge (ID/severity) + title",
      row2: "subtitle / family / device / domain",
      row3: "progress bar (score-based fill)",
      row4: "meta row: score value + status badge"
    },
    variants: [
      { id: "control-card", context: "SOC2 controls", badge_field: "control_id", score_field: "posture_score" },
      { id: "alert-card", context: "Alert feed", badge_field: "severity", score_field: "risk_amount" },
      { id: "course-card", context: "Cornerstone LMS", badge_field: "course_type", score_field: "completion_pct" },
      { id: "position-card", context: "Workday HR", badge_field: "req_status", score_field: "days_open" },
      { id: "employee-card", context: "Workday/Cornerstone", badge_field: "compliance_status", score_field: "training_score" }
    ]
  },
  detail_section: {
    id: "detail_section",
    name: "Detail Section Block",
    category: "component",
    description: "Stacked section in the detail panel. Mono label header + content. Separated by border-bottom.",
    extracted_from: ["demo1", "demo2"],
    css_pattern: "padding:.85rem 1rem; border-bottom:1px solid var(--rule)",
    variants: [
      { id: "score-hero", content: "Big score number + posture label + frameworks" },
      { id: "signal-list", content: "Signal rows with name + bar + value + status badge" },
      { id: "causal-path", content: "Mono chain: signal → signal → score" },
      { id: "gap-box", content: "Amber-bordered compliance gap description" },
      { id: "evidence-list", content: "Evidence items with auto/manual icon + record count" },
      { id: "info-grid", content: "2-col grid of key-value pairs" },
      { id: "remediation-list", content: "Ordered action items with → prefix" },
      { id: "description-block", content: "Rich text description paragraph" }
    ]
  },
  stat_cell: {
    id: "stat_cell",
    name: "Stat Cell",
    category: "component",
    description: "Single KPI cell within the posture strip. Big display-font value (color-coded) + mono label.",
    extracted_from: ["demo2"],
    css_pattern: "padding:.75rem 1rem; text-align:center; border-right:1px solid var(--rule)",
    anatomy: {
      value: "font-family:var(--disp); font-size:1.6rem; font-weight:700",
      label: "font-family:var(--mono); font-size:.58rem; text-transform:uppercase; letter-spacing:.1em"
    }
  },
  signal_meter: {
    id: "signal_meter",
    name: "Signal Meter Row",
    category: "component",
    description: "Individual signal reading: name + progress bar + value + status badge. Used in both dashboards for L0 signals.",
    extracted_from: ["demo1", "demo2"],
    css_pattern: "display:grid; grid-template-columns:1fr auto auto; gap:.5rem; align-items:center",
    anatomy: {
      name: "mono .68rem, muted color",
      bar: "60-80px width, 5px height, color-coded fill",
      value: "mono .68rem, bold, color-coded",
      status: "optional pass/warn/fail badge"
    }
  },
  chat_panel: {
    id: "chat_panel",
    name: "AI Chat Panel",
    category: "compound",
    description: "Right-side panel with: message list (scrollable) + suggestion chips + text input + send button. Messages styled as user (blue bg) vs AI (surface bg).",
    extracted_from: ["demo1", "demo2"],
    slots: ["messages", "suggestions", "input_bar"],
    anatomy: {
      empty_state: "icon + title + description centered",
      user_msg: "align-self:flex-end; blue tinted bg",
      ai_msg: "align-self:flex-start; surface bg; supports bold, code, markdown",
      suggestions: "flex-wrap chip buttons below messages",
      input: "textarea + send button in fixed footer"
    }
  },
  empty_state: {
    id: "empty_state",
    name: "Empty State",
    category: "component",
    description: "Centered placeholder when no item is selected. Display-font icon + mono title + description.",
    extracted_from: ["demo1", "demo2"],
    anatomy: {
      icon: "display font, large (2-3rem), muted",
      title: "mono, .75rem, muted",
      description: "sans, .8rem, muted, max-width:220px"
    }
  },
  status_badge: {
    id: "status_badge",
    name: "Status Badge",
    category: "atom",
    description: "Inline status indicator with dot + label. Color-coded: pass=green, warn=amber, fail=red.",
    extracted_from: ["demo1", "demo2"],
    css_pattern: "display:inline-flex; align-items:center; gap:.3rem; font-family:var(--mono); font-size:.6rem; padding:.15rem .5rem; border:1px solid",
    variants: {
      pass: { bg: "var(--green-bg)", border: "var(--green-b)", color: "var(--green2)" },
      warn: { bg: "var(--amber-bg)", border: "var(--amber-b)", color: "var(--amber2)" },
      fail: { bg: "var(--red-bg)", border: "var(--red-b)", color: "var(--red2)" },
      info: { bg: "var(--blue-bg)", border: "var(--blue-b)", color: "var(--blue2)" }
    }
  },
  causal_graph_svg: {
    id: "causal_graph_svg",
    name: "Causal Graph SVG",
    category: "visualization",
    description: "Directed acyclic graph rendered as SVG. Nodes are colored circles with labels, edges show causal direction with arrow markers. VETO gates highlighted in red.",
    extracted_from: ["demo1"],
    config: { height: "260px", width: "100%", node_radius: 22 }
  }
};

// ── LAYOUT TEMPLATES (composable from primitives) ─────────────────
const LAYOUT_TEMPLATES = {
  "command-center": {
    id: "command-center",
    name: "Command Center",
    description: "Full 3-panel layout with posture strip. Master/detail/chat. The primary CCE layout.",
    primitives: ["topbar", "posture_strip", "three_panel"],
    panel_config: {
      left: ["filter_bar", "list_card*"],
      center: ["detail_section*", "signal_meter*", "causal_graph_svg"],
      right: ["chat_panel"]
    },
    best_for: ["SOC2 monitoring", "Alert intelligence", "Compliance posture", "Security operations"],
    theme_recommendation: "light for compliance, dark for operations"
  },
  "triage-focused": {
    id: "triage-focused",
    name: "Triage Focused",
    description: "3-panel with NO posture strip. Maximizes vertical space for alert lists and investigation.",
    primitives: ["topbar", "three_panel"],
    panel_config: {
      left: ["filter_bar", "list_card*"],
      center: ["causal_graph_svg", "detail_section*"],
      right: ["chat_panel"]
    },
    best_for: ["Incident response", "Alert triage", "Active investigations"],
    theme_recommendation: "dark"
  },
  "posture-overview": {
    id: "posture-overview",
    name: "Posture Overview",
    description: "Wide posture strip (6-8 KPIs) + 2-panel below. No chat — pure monitoring view.",
    primitives: ["topbar", "posture_strip", "two_panel"],
    panel_config: {
      left: ["list_card*"],
      right: ["panel_with_tabs", "detail_section*"]
    },
    best_for: ["Executive dashboards", "Audit prep", "Compliance overview", "Board reporting"],
    theme_recommendation: "light"
  },
  "lms-training": {
    id: "lms-training",
    name: "LMS Training Dashboard",
    description: "Cornerstone/Workday training management. KPI bar for completion metrics + course/employee list + detail + advisor chat.",
    primitives: ["topbar", "posture_strip", "three_panel"],
    panel_config: {
      left: ["filter_bar", "list_card*"],
      center: ["detail_section*", "signal_meter*"],
      right: ["chat_panel"]
    },
    posture_strip_config: {
      cells: ["Training Completion %", "Overdue Certs", "Active Learners", "HIPAA Compliance", "Avg Days to Complete", "Courses Published"]
    },
    filter_config: ["All", "Overdue", "In Progress", "Completed", "Expiring Soon"],
    best_for: ["Cornerstone LMS management", "Training compliance", "Certification tracking"],
    theme_recommendation: "light"
  },
  "hr-workforce": {
    id: "hr-workforce",
    name: "HR Workforce Dashboard",
    description: "Workday HR operations. KPI bar for workforce metrics + employee/position list + detail + AI advisor.",
    primitives: ["topbar", "posture_strip", "three_panel"],
    panel_config: {
      left: ["filter_bar", "list_card*"],
      center: ["detail_section*", "info_grid"],
      right: ["chat_panel"]
    },
    posture_strip_config: {
      cells: ["Headcount", "Open Reqs", "Time-to-Hire", "Turnover Rate", "Pending Actions", "Compliance Score"]
    },
    filter_config: ["All", "Active", "On Leave", "Terminated", "Pending"],
    best_for: ["Workday HR management", "Workforce analytics", "Employee lifecycle"],
    theme_recommendation: "light"
  },
  "hybrid-compliance": {
    id: "hybrid-compliance",
    name: "Hybrid Compliance (Cornerstone + Workday + Security)",
    description: "Cross-domain view linking Cornerstone training, Workday HR events, and security signals into a unified compliance surface.",
    primitives: ["topbar", "posture_strip", "three_panel"],
    panel_config: {
      left: ["filter_bar", "list_card*"],
      center: ["panel_with_tabs", "causal_graph_svg", "detail_section*", "signal_meter*"],
      right: ["chat_panel"]
    },
    posture_strip_config: {
      cells: ["HIPAA Posture", "Deprov. Lag", "Cert Compliance", "Access Reviews", "Training Gap", "Risk Score"]
    },
    filter_config: ["All", "Critical", "Degraded", "Passing", "Security", "HR", "Training"],
    tab_config: ["Causal Path", "Signals", "Evidence", "Cross-Domain Links"],
    best_for: ["HIPAA compliance spanning HR/Training/Security", "SOC2 controls with HR dependencies", "Unified GRC view"],
    theme_recommendation: "light or dark based on operator role"
  },
  "migration-tracker": {
    id: "migration-tracker",
    name: "Data Migration Tracker",
    description: "SumTotal→Cornerstone or system migration tracking. KPI bar for migration progress + table mapping list + detail panel.",
    primitives: ["topbar", "posture_strip", "two_panel"],
    panel_config: {
      left: ["filter_bar", "list_card*"],
      right: ["detail_section*", "signal_meter*"]
    },
    posture_strip_config: {
      cells: ["Tables Mapped", "Fields Migrated", "Confidence Score", "Errors", "In Progress", "Completion %"]
    },
    best_for: ["SumTotal to Cornerstone migration", "System cutover dashboards", "ETL monitoring"],
    theme_recommendation: "light"
  }
};

// ── DOMAIN CONTEXTS ───────────────────────────────────────────────
const DOMAIN_CONTEXTS = {
  security: {
    name: "Security Operations",
    list_item_anatomy: { badge: "severity|control_id", title: "alert_name|control_title", subtitle: "device|family", score: "risk_amount|posture_score", status: "pass|warn|fail|critical|high|medium|low" },
    detail_sections: ["score-hero", "causal-path", "signal-list", "gap-box", "evidence-list", "remediation-list"],
    chat_system_prompt_focus: "compliance posture, MITRE ATT&CK, SOC2 controls, risk quantification"
  },
  cornerstone: {
    name: "Cornerstone OnDemand LMS",
    list_item_anatomy: { badge: "course_type|cert_status", title: "course_name|employee_name", subtitle: "department|due_date", score: "completion_pct|days_overdue", status: "completed|in_progress|overdue|not_started|expiring" },
    detail_sections: ["score-hero", "description-block", "signal-list", "info-grid", "evidence-list"],
    chat_system_prompt_focus: "training compliance, HIPAA certification, learning analytics, completion forecasting"
  },
  workday: {
    name: "Workday HCM",
    list_item_anatomy: { badge: "req_status|employee_status", title: "position_title|employee_name", subtitle: "department|location", score: "days_open|performance_score", status: "open|filled|pending|approved|closed" },
    detail_sections: ["score-hero", "info-grid", "description-block", "signal-list"],
    chat_system_prompt_focus: "workforce planning, HR compliance, employee lifecycle, onboarding/offboarding SLA"
  },
  hybrid: {
    name: "Cross-Domain Compliance",
    list_item_anatomy: { badge: "domain_source|severity", title: "finding_title", subtitle: "source_system|control_family", score: "composite_risk|posture_score", status: "critical|degraded|passing|not_evaluated" },
    detail_sections: ["score-hero", "causal-path", "signal-list", "gap-box", "evidence-list", "remediation-list", "info-grid"],
    chat_system_prompt_focus: "cross-domain causal analysis, HIPAA/SOC2 unified posture, HR-to-security signal correlation"
  }
};


// ═══════════════════════════════════════════════════════════════════
// INTERACTIVE REGISTRY VIEWER
// ═══════════════════════════════════════════════════════════════════

const TABS = ["Strategy", "Primitives", "Templates", "Domains", "Builder"];

// mini preview boxes
const PanelPreview = ({left, center, right, strip, theme}) => {
  const dk = theme === "dark";
  const bg = dk ? "#0a0f1e" : "#faf9f7";
  const surf = dk ? "#131d30" : "#ffffff";
  const rule = dk ? "#1e2d47" : "#e7e3dd";
  const accent = dk ? "#3b82f6" : "#1e40af";
  const txt = dk ? "#6a82a8" : "#78716c";
  const g = dk ? "#22c55e" : "#16a34a";
  const r = dk ? "#ef4444" : "#dc2626";
  const a = dk ? "#f97316" : "#d97706";

  return (
    <div style={{border:`1px solid ${rule}`, borderRadius:4, overflow:"hidden", background:bg, fontSize:9, fontFamily:"monospace"}}>
      {/* topbar */}
      <div style={{height:18, background: dk?"#05080f":"#1c1917", display:"flex", alignItems:"center", padding:"0 6px", gap:4}}>
        <span style={{color:"#fff", fontSize:7, fontWeight:700}}>CCE</span>
        <span style={{color:txt, fontSize:6}}>Dashboard</span>
        <div style={{marginLeft:"auto", width:4, height:4, borderRadius:"50%", background:g}}/>
      </div>
      {/* strip */}
      {strip && (
        <div style={{display:"grid", gridTemplateColumns:`repeat(${strip.length},1fr)`, borderBottom:`1px solid ${rule}`, background:surf}}>
          {strip.map((s,i)=>(
            <div key={i} style={{padding:"4px 3px", textAlign:"center", borderRight: i<strip.length-1?`1px solid ${rule}`:"none"}}>
              <div style={{fontSize:10, fontWeight:700, color: i===0?g:i===2?a:i===3?r:accent}}>{s.v}</div>
              <div style={{fontSize:5, color:txt, textTransform:"uppercase", letterSpacing:".5px"}}>{s.l}</div>
            </div>
          ))}
        </div>
      )}
      {/* panels */}
      <div style={{display:"grid", gridTemplateColumns: right ? "30% 1fr 28%" : "35% 1fr", height:strip?110:128}}>
        {/* left */}
        <div style={{borderRight:`1px solid ${rule}`, padding:3, overflow:"hidden"}}>
          <div style={{fontSize:5, color:txt, textTransform:"uppercase", marginBottom:3, letterSpacing:".5px"}}>{left?.title||"List"}</div>
          {[0,1,2,3].map(i=>(
            <div key={i} style={{padding:"2px 3px", marginBottom:2, borderBottom:`1px solid ${rule}`, background: i===1?dk?"rgba(59,130,246,.1)":"#eff6ff":"transparent", borderLeft: i===1?`2px solid ${accent}`:"2px solid transparent"}}>
              <div style={{display:"flex", gap:2, alignItems:"center"}}>
                <span style={{fontSize:5, background: i===0?g:i===2?a:i===3?r:accent, color:"#fff", padding:"0 2px", lineHeight:"10px"}}>{left?.badges?.[i]||"ID"}</span>
                <span style={{fontSize:6, color: dk?"#fff":"#1c1917"}}>{left?.items?.[i]||`Item ${i+1}`}</span>
              </div>
              <div style={{height:2, background:rule, marginTop:2}}>
                <div style={{height:2, width:`${80-i*15}%`, background: i===3?r:i===2?a:g}}/>
              </div>
            </div>
          ))}
        </div>
        {/* center */}
        <div style={{borderRight: right?`1px solid ${rule}`:"none", padding:3, overflow:"hidden"}}>
          <div style={{fontSize:5, color:txt, textTransform:"uppercase", marginBottom:3, letterSpacing:".5px"}}>{center?.title||"Detail"}</div>
          <div style={{fontSize:16, fontWeight:700, color:g, lineHeight:1}}>84<span style={{fontSize:8}}>%</span></div>
          <div style={{fontSize:5, color:txt, marginBottom:4}}>Posture Score</div>
          {center?.signals?.map((s,i)=>(
            <div key={i} style={{display:"flex", gap:3, alignItems:"center", marginBottom:2}}>
              <span style={{fontSize:5, color:txt, flex:1}}>{s}</span>
              <div style={{width:30, height:3, background:rule}}>
                <div style={{height:3, width:`${70+i*10}%`, background: i===2?r:i===1?a:g}}/>
              </div>
            </div>
          ))||null}
          {center?.graph && (
            <div style={{background:dk?"#0f1627":"#f4f2ee", border:`1px solid ${rule}`, padding:3, marginTop:3, textAlign:"center"}}>
              <div style={{display:"flex", justifyContent:"center", gap:6, alignItems:"center"}}>
                {["○","→","◆","→","□"].map((n,i)=>(
                  <span key={i} style={{fontSize:8, color: i===2?r:accent}}>{n}</span>
                ))}
              </div>
              <div style={{fontSize:5, color:txt, marginTop:2}}>Causal Graph</div>
            </div>
          )}
        </div>
        {/* right */}
        {right && (
          <div style={{padding:3, overflow:"hidden", display:"flex", flexDirection:"column"}}>
            <div style={{fontSize:5, color:txt, textTransform:"uppercase", marginBottom:3, letterSpacing:".5px"}}>{right?.title||"Chat"}</div>
            <div style={{flex:1}}>
              <div style={{background:dk?"rgba(59,130,246,.1)":"#eff6ff", border:`1px solid ${dk?"rgba(59,130,246,.3)":"#bfdbfe"}`, padding:2, marginBottom:2, fontSize:5, marginLeft:8}}>User question</div>
              <div style={{background:surf, border:`1px solid ${rule}`, padding:2, marginBottom:2, fontSize:5, marginRight:8}}>AI response…</div>
            </div>
            <div style={{display:"flex", gap:2, marginTop:2}}>
              <div style={{flex:1, height:12, background:dk?surf:"#f4f2ee", border:`1px solid ${rule}`}}/>
              <div style={{width:20, height:12, background:accent, display:"flex", alignItems:"center", justifyContent:"center"}}>
                <span style={{fontSize:5, color:"#fff"}}>→</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default function DashboardLayoutRegistry() {
  const [tab, setTab] = useState("Strategy");
  const [selectedTemplate, setSelectedTemplate] = useState("command-center");
  const [selectedDomain, setSelectedDomain] = useState("security");
  const [selectedTheme, setSelectedTheme] = useState("light");
  const [expandedPrimitive, setExpandedPrimitive] = useState(null);

  const tpl = LAYOUT_TEMPLATES[selectedTemplate];
  const domain = DOMAIN_CONTEXTS[selectedDomain];
  const theme = THEMES[selectedTheme];

  return (
    <div style={{fontFamily:"'IBM Plex Mono', monospace", background:"#0a0a0a", color:"#c4c4c4", minHeight:"100vh", display:"flex", flexDirection:"column"}}>
      {/* Header */}
      <div style={{background:"#111", borderBottom:"1px solid #222", padding:"12px 20px", display:"flex", alignItems:"center", gap:12}}>
        <span style={{fontSize:13, fontWeight:700, color:"#fff", letterSpacing:".08em"}}>CCE LAYOUT REGISTRY</span>
        <span style={{fontSize:10, color:"#555", letterSpacing:".1em"}}>DESIGN STRATEGY & DYNAMIC TEMPLATES</span>
        <div style={{marginLeft:"auto", display:"flex", gap:8}}>
          <span style={{fontSize:9, color:"#3b82f6"}}>v2.0</span>
          <span style={{fontSize:9, color:"#555"}}>{Object.keys(LAYOUT_PRIMITIVES).length} primitives · {Object.keys(LAYOUT_TEMPLATES).length} templates · {Object.keys(DOMAIN_CONTEXTS).length} domains</span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{display:"flex", borderBottom:"1px solid #222", background:"#0f0f0f"}}>
        {TABS.map(t=>(
          <button key={t} onClick={()=>setTab(t)} style={{
            padding:"10px 18px", fontSize:10, letterSpacing:".1em", textTransform:"uppercase",
            background:"transparent", border:"none", borderBottom: t===tab?"2px solid #3b82f6":"2px solid transparent",
            color: t===tab?"#3b82f6":"#555", cursor:"pointer", fontFamily:"inherit", marginBottom:-1
          }}>{t}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{flex:1, overflow:"auto", padding:20}}>

        {/* ── STRATEGY TAB ──────────────────────── */}
        {tab === "Strategy" && (
          <div style={{maxWidth:900}}>
            <h2 style={{fontSize:16, color:"#fff", marginBottom:4, fontWeight:700}}>Dynamic Dashboard Generation Strategy</h2>
            <p style={{fontSize:11, color:"#777", marginBottom:20, lineHeight:1.7}}>
              Architecture for building context-aware dashboards from composable primitives across Security, Cornerstone LMS, Workday HCM, and cross-domain compliance surfaces.
            </p>

            {/* Architecture Diagram */}
            <div style={{background:"#111", border:"1px solid #222", padding:16, marginBottom:20}}>
              <div style={{fontSize:9, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:12}}>Generation Pipeline</div>
              <div style={{display:"flex", gap:8, alignItems:"stretch", flexWrap:"wrap"}}>
                {[
                  {label:"User Context", desc:"Domain, role, data sources, compliance frameworks", color:"#3b82f6"},
                  {label:"Template Selection", desc:"Match context → layout template via scoring heuristics", color:"#8b5cf6"},
                  {label:"Primitive Assembly", desc:"Compose topbar + strip + panels + components from registry", color:"#f97316"},
                  {label:"Domain Binding", desc:"Bind list cards, detail sections, metrics to domain schema", color:"#22c55e"},
                  {label:"Theme Application", desc:"Apply light/dark theme tokens based on operator role", color:"#ef4444"},
                  {label:"Render", desc:"Generate HTML/React with CSS vars + data bindings", color:"#eab308"}
                ].map((s,i)=>(
                  <div key={i} style={{flex:1, minWidth:120, background:"#0a0a0a", border:`1px solid ${s.color}33`, padding:10}}>
                    <div style={{display:"flex", alignItems:"center", gap:4, marginBottom:4}}>
                      <span style={{fontSize:8, color:s.color, fontWeight:700}}>{String(i+1).padStart(2,"0")}</span>
                      <span style={{fontSize:9, color:"#fff", fontWeight:600}}>{s.label}</span>
                    </div>
                    <div style={{fontSize:8, color:"#666", lineHeight:1.5}}>{s.desc}</div>
                    {i < 5 && <div style={{textAlign:"right", fontSize:10, color:"#333", marginTop:4}}>→</div>}
                  </div>
                ))}
              </div>
            </div>

            {/* Key Principles */}
            <div style={{fontSize:10, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:8}}>Key Design Principles</div>
            {[
              {title:"Composable Primitives", desc:"Every layout is assembled from 14 atomic primitives (topbar, posture_strip, three_panel, list_card, etc.). No monolithic templates — primitives compose freely."},
              {title:"Domain-Agnostic Scaffolds", desc:"The three_panel and two_panel scaffolds are domain-agnostic. Domain specificity comes from binding list_card anatomy, detail_section variants, and filter_bar options to domain schemas."},
              {title:"Theme as Context Signal", desc:"Light theme signals 'compliance/audit/executive' context. Dark theme signals 'operations/triage/real-time'. Theme selection is a function of operator role, not preference."},
              {title:"Causal Chat as First-Class Panel", desc:"The AI chat panel is not an add-on — it's a core layout primitive. Every 3-panel template reserves the right column for contextual AI investigation."},
              {title:"Posture Strip = Executive Attention Layer", desc:"The KPI strip is the attention anchor. Its cells are domain-specific but structurally identical. 3-8 cells, each: big value (display font, color-coded) + mono label."},
              {title:"Progressive Detail Disclosure", desc:"List → Select → Detail → Signals → Chat. The interaction model is identical across all domains. Only the data ontology changes."},
            ].map((p,i)=>(
              <div key={i} style={{background:"#111", border:"1px solid #1a1a1a", padding:"10px 14px", marginBottom:6}}>
                <div style={{fontSize:10, color:"#fff", fontWeight:600, marginBottom:3}}>{p.title}</div>
                <div style={{fontSize:9, color:"#777", lineHeight:1.6}}>{p.desc}</div>
              </div>
            ))}

            {/* Cross-Domain Strategy */}
            <div style={{fontSize:10, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:8, marginTop:20}}>Cross-Domain Template Mapping</div>
            <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:8}}>
              {Object.entries(DOMAIN_CONTEXTS).map(([id, d])=>(
                <div key={id} style={{background:"#111", border:"1px solid #1a1a1a", padding:12}}>
                  <div style={{fontSize:10, color:"#3b82f6", fontWeight:600, marginBottom:6}}>{d.name}</div>
                  <div style={{fontSize:8, color:"#555", marginBottom:4}}>LIST CARD BADGE → <span style={{color:"#aaa"}}>{d.list_item_anatomy.badge}</span></div>
                  <div style={{fontSize:8, color:"#555", marginBottom:4}}>DETAIL SECTIONS → <span style={{color:"#aaa"}}>{d.detail_sections.join(", ")}</span></div>
                  <div style={{fontSize:8, color:"#555"}}>CHAT FOCUS → <span style={{color:"#aaa"}}>{d.chat_system_prompt_focus}</span></div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── PRIMITIVES TAB ────────────────────── */}
        {tab === "Primitives" && (
          <div>
            <h2 style={{fontSize:14, color:"#fff", marginBottom:12}}>Layout Primitives ({Object.keys(LAYOUT_PRIMITIVES).length})</h2>
            <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:8}}>
              {Object.values(LAYOUT_PRIMITIVES).map(p=>(
                <div key={p.id}
                  onClick={()=>setExpandedPrimitive(expandedPrimitive===p.id?null:p.id)}
                  style={{background:"#111", border: expandedPrimitive===p.id?"1px solid #3b82f6":"1px solid #1a1a1a", padding:12, cursor:"pointer", transition:"border .15s"}}>
                  <div style={{display:"flex", alignItems:"center", gap:6, marginBottom:4}}>
                    <span style={{fontSize:8, color:"#3b82f6", background:"rgba(59,130,246,.1)", padding:"2px 6px", border:"1px solid rgba(59,130,246,.2)"}}>{p.category}</span>
                    <span style={{fontSize:10, color:"#fff", fontWeight:600}}>{p.name}</span>
                  </div>
                  <div style={{fontSize:9, color:"#777", lineHeight:1.5, marginBottom:6}}>{p.description}</div>
                  {p.extracted_from && (
                    <div style={{fontSize:8, color:"#444"}}>Source: {p.extracted_from.join(", ")}</div>
                  )}
                  {expandedPrimitive === p.id && (
                    <div style={{marginTop:8, borderTop:"1px solid #222", paddingTop:8}}>
                      {p.css_pattern && <div style={{fontSize:8, color:"#22c55e", marginBottom:4}}>CSS: {p.css_pattern}</div>}
                      {p.slots && <div style={{fontSize:8, color:"#f97316", marginBottom:4}}>Slots: {p.slots.join(" · ")}</div>}
                      {p.anatomy && (
                        <div style={{marginTop:4}}>
                          {Object.entries(p.anatomy).map(([k,v])=>(
                            <div key={k} style={{fontSize:8, color:"#555", marginBottom:2}}>
                              <span style={{color:"#8b5cf6"}}>{k}:</span> {typeof v === "string" ? v : JSON.stringify(v)}
                            </div>
                          ))}
                        </div>
                      )}
                      {p.variants && Array.isArray(p.variants) && (
                        <div style={{marginTop:4}}>
                          <div style={{fontSize:8, color:"#555", marginBottom:2}}>Variants:</div>
                          {p.variants.map((v,i)=>(
                            <div key={i} style={{fontSize:8, color:"#666", marginLeft:8}}>• {v.id || v.context || JSON.stringify(v)}</div>
                          ))}
                        </div>
                      )}
                      {p.domain_examples && (
                        <div style={{marginTop:4}}>
                          <div style={{fontSize:8, color:"#555", marginBottom:2}}>Domain Examples:</div>
                          {Object.entries(p.domain_examples).map(([dk,dv])=>(
                            <div key={dk} style={{fontSize:8, color:"#666", marginLeft:8}}>
                              <span style={{color:"#eab308"}}>{dk}:</span> {dv.join(" · ")}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── TEMPLATES TAB ─────────────────────── */}
        {tab === "Templates" && (
          <div>
            <h2 style={{fontSize:14, color:"#fff", marginBottom:12}}>Layout Templates ({Object.keys(LAYOUT_TEMPLATES).length})</h2>
            <div style={{display:"flex", gap:6, marginBottom:16, flexWrap:"wrap"}}>
              {Object.values(LAYOUT_TEMPLATES).map(t=>(
                <button key={t.id} onClick={()=>setSelectedTemplate(t.id)} style={{
                  padding:"6px 12px", fontSize:9, letterSpacing:".06em",
                  background: selectedTemplate===t.id?"rgba(59,130,246,.15)":"transparent",
                  border: selectedTemplate===t.id?"1px solid #3b82f6":"1px solid #333",
                  color: selectedTemplate===t.id?"#3b82f6":"#666",
                  cursor:"pointer", fontFamily:"inherit"
                }}>{t.name}</button>
              ))}
            </div>

            <div style={{display:"grid", gridTemplateColumns:"1fr 280px", gap:16}}>
              <div>
                <div style={{background:"#111", border:"1px solid #1a1a1a", padding:16}}>
                  <div style={{fontSize:12, color:"#fff", fontWeight:700, marginBottom:4}}>{tpl.name}</div>
                  <div style={{fontSize:9, color:"#777", lineHeight:1.6, marginBottom:12}}>{tpl.description}</div>

                  <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Primitives Used</div>
                  <div style={{display:"flex", gap:4, flexWrap:"wrap", marginBottom:12}}>
                    {tpl.primitives.map(p=>(
                      <span key={p} style={{fontSize:8, padding:"2px 6px", background:"rgba(139,92,246,.1)", border:"1px solid rgba(139,92,246,.2)", color:"#8b5cf6"}}>{p}</span>
                    ))}
                  </div>

                  <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Panel Configuration</div>
                  <div style={{display:"grid", gridTemplateColumns: tpl.panel_config.right?"1fr 1fr 1fr":"1fr 1fr", gap:6, marginBottom:12}}>
                    {Object.entries(tpl.panel_config).map(([panel, components])=>(
                      <div key={panel} style={{background:"#0a0a0a", border:"1px solid #222", padding:8}}>
                        <div style={{fontSize:8, color:"#3b82f6", fontWeight:600, marginBottom:4, textTransform:"uppercase"}}>{panel}</div>
                        {components.map((c,i)=>(
                          <div key={i} style={{fontSize:8, color:"#777", marginBottom:2}}>• {c}</div>
                        ))}
                      </div>
                    ))}
                  </div>

                  <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Best For</div>
                  <div style={{display:"flex", gap:4, flexWrap:"wrap", marginBottom:12}}>
                    {tpl.best_for.map(b=>(
                      <span key={b} style={{fontSize:8, padding:"2px 6px", background:"rgba(34,197,94,.08)", border:"1px solid rgba(34,197,94,.2)", color:"#22c55e"}}>{b}</span>
                    ))}
                  </div>

                  {tpl.posture_strip_config && (
                    <>
                      <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Posture Strip Cells</div>
                      <div style={{display:"flex", gap:4, flexWrap:"wrap", marginBottom:12}}>
                        {tpl.posture_strip_config.cells.map(c=>(
                          <span key={c} style={{fontSize:8, padding:"2px 6px", background:"rgba(234,179,8,.08)", border:"1px solid rgba(234,179,8,.15)", color:"#eab308"}}>{c}</span>
                        ))}
                      </div>
                    </>
                  )}

                  <div style={{fontSize:8, color:"#555"}}>Theme: <span style={{color:"#aaa"}}>{tpl.theme_recommendation}</span></div>
                </div>
              </div>

              {/* Preview */}
              <div>
                <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Preview (Light)</div>
                <PanelPreview
                  theme="light"
                  strip={tpl.primitives.includes("posture_strip") ? (tpl.posture_strip_config?.cells||["Score","Controls","Degraded","Critical","Evidence","Audit"]).slice(0,6).map((c,i)=>({v:i===0?"84%":i===1?"9/9":i===2?"3":i===3?"1":i===4?"83%":"87d",l:c})) : null}
                  left={{title:tpl.panel_config.left?.includes("filter_bar")?"Filtered List":"Items", items:["Item Alpha","Item Beta","Item Gamma","Item Delta"], badges:["P","W","W","F"]}}
                  center={{title:"Detail", signals:["signal_alpha","signal_beta","signal_gamma"], graph: tpl.panel_config.center?.includes("causal_graph_svg")}}
                  right={tpl.panel_config.right ? {title: tpl.panel_config.right.includes("chat_panel")?"AI Advisor":"Actions"} : null}
                />
                <div style={{height:12}}/>
                <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Preview (Dark)</div>
                <PanelPreview
                  theme="dark"
                  strip={tpl.primitives.includes("posture_strip") ? (tpl.posture_strip_config?.cells||["Score","Controls","Degraded","Critical","Evidence","Audit"]).slice(0,6).map((c,i)=>({v:i===0?"84%":i===1?"9/9":i===2?"3":i===3?"1":i===4?"83%":"87d",l:c})) : null}
                  left={{title:"Active Items", items:["Alert Alpha","Alert Beta","Alert Gamma","Alert Delta"], badges:["C","H","M","L"]}}
                  center={{title:"Investigation", signals:["ioc_match","lateral_mvmt","defense_evasion"], graph: tpl.panel_config.center?.includes("causal_graph_svg")}}
                  right={tpl.panel_config.right ? {title:"Investigation Chat"} : null}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── DOMAINS TAB ───────────────────────── */}
        {tab === "Domains" && (
          <div>
            <h2 style={{fontSize:14, color:"#fff", marginBottom:12}}>Domain Contexts ({Object.keys(DOMAIN_CONTEXTS).length})</h2>
            <div style={{display:"flex", gap:6, marginBottom:16}}>
              {Object.entries(DOMAIN_CONTEXTS).map(([id, d])=>(
                <button key={id} onClick={()=>setSelectedDomain(id)} style={{
                  padding:"6px 12px", fontSize:9,
                  background: selectedDomain===id?"rgba(59,130,246,.15)":"transparent",
                  border: selectedDomain===id?"1px solid #3b82f6":"1px solid #333",
                  color: selectedDomain===id?"#3b82f6":"#666",
                  cursor:"pointer", fontFamily:"inherit"
                }}>{d.name}</button>
              ))}
            </div>

            <div style={{background:"#111", border:"1px solid #1a1a1a", padding:16, marginBottom:16}}>
              <div style={{fontSize:12, color:"#fff", fontWeight:700, marginBottom:8}}>{domain.name}</div>

              <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>List Card Anatomy</div>
              <div style={{display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:6, marginBottom:16}}>
                {Object.entries(domain.list_item_anatomy).map(([field, values])=>(
                  <div key={field} style={{background:"#0a0a0a", border:"1px solid #222", padding:8}}>
                    <div style={{fontSize:8, color:"#8b5cf6", fontWeight:600, marginBottom:3, textTransform:"uppercase"}}>{field}</div>
                    <div style={{fontSize:8, color:"#777"}}>{values}</div>
                  </div>
                ))}
              </div>

              <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Detail Sections</div>
              <div style={{display:"flex", gap:4, flexWrap:"wrap", marginBottom:16}}>
                {domain.detail_sections.map(s=>(
                  <span key={s} style={{fontSize:8, padding:"3px 8px", background:"rgba(249,115,22,.08)", border:"1px solid rgba(249,115,22,.15)", color:"#f97316"}}>{s}</span>
                ))}
              </div>

              <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Chat System Prompt Focus</div>
              <div style={{fontSize:9, color:"#22c55e", lineHeight:1.6, background:"#0a0a0a", border:"1px solid #222", padding:8}}>{domain.chat_system_prompt_focus}</div>
            </div>

            {/* Compatible Templates */}
            <div style={{fontSize:10, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:8}}>Compatible Templates for {domain.name}</div>
            <div style={{display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:8}}>
              {Object.values(LAYOUT_TEMPLATES).filter(t=>
                t.best_for.some(b=>b.toLowerCase().includes(selectedDomain)) ||
                selectedDomain === "hybrid" ||
                (selectedDomain === "security" && (t.id==="command-center"||t.id==="triage-focused"||t.id==="posture-overview")) ||
                (selectedDomain === "cornerstone" && (t.id==="lms-training"||t.id==="hybrid-compliance"||t.id==="migration-tracker")) ||
                (selectedDomain === "workday" && (t.id==="hr-workforce"||t.id==="hybrid-compliance"))
              ).map(t=>(
                <div key={t.id} style={{background:"#111", border:"1px solid #1a1a1a", padding:10}}>
                  <div style={{fontSize:10, color:"#fff", fontWeight:600, marginBottom:3}}>{t.name}</div>
                  <div style={{fontSize:8, color:"#666", lineHeight:1.5}}>{t.description.slice(0,120)}…</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── BUILDER TAB ───────────────────────── */}
        {tab === "Builder" && (
          <div>
            <h2 style={{fontSize:14, color:"#fff", marginBottom:4}}>Template Builder</h2>
            <p style={{fontSize:9, color:"#666", marginBottom:16}}>Select domain + template + theme to see the full generation spec.</p>

            <div style={{display:"flex", gap:12, marginBottom:16}}>
              <div>
                <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:4}}>Domain</div>
                <div style={{display:"flex", gap:4}}>
                  {Object.entries(DOMAIN_CONTEXTS).map(([id,d])=>(
                    <button key={id} onClick={()=>setSelectedDomain(id)} style={{
                      padding:"4px 10px", fontSize:8,
                      background: selectedDomain===id?"rgba(59,130,246,.15)":"transparent",
                      border: selectedDomain===id?"1px solid #3b82f6":"1px solid #333",
                      color: selectedDomain===id?"#3b82f6":"#555", cursor:"pointer", fontFamily:"inherit"
                    }}>{d.name}</button>
                  ))}
                </div>
              </div>
              <div>
                <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:4}}>Template</div>
                <div style={{display:"flex", gap:4, flexWrap:"wrap"}}>
                  {Object.values(LAYOUT_TEMPLATES).map(t=>(
                    <button key={t.id} onClick={()=>setSelectedTemplate(t.id)} style={{
                      padding:"4px 10px", fontSize:8,
                      background: selectedTemplate===t.id?"rgba(139,92,246,.15)":"transparent",
                      border: selectedTemplate===t.id?"1px solid #8b5cf6":"1px solid #333",
                      color: selectedTemplate===t.id?"#8b5cf6":"#555", cursor:"pointer", fontFamily:"inherit"
                    }}>{t.name}</button>
                  ))}
                </div>
              </div>
              <div>
                <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:4}}>Theme</div>
                <div style={{display:"flex", gap:4}}>
                  {Object.values(THEMES).map(t=>(
                    <button key={t.id} onClick={()=>setSelectedTheme(t.id)} style={{
                      padding:"4px 10px", fontSize:8,
                      background: selectedTheme===t.id?"rgba(234,179,8,.15)":"transparent",
                      border: selectedTheme===t.id?"1px solid #eab308":"1px solid #333",
                      color: selectedTheme===t.id?"#eab308":"#555", cursor:"pointer", fontFamily:"inherit"
                    }}>{t.name}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* Generated Spec */}
            <div style={{display:"grid", gridTemplateColumns:"1fr 320px", gap:16}}>
              <div style={{background:"#111", border:"1px solid #1a1a1a", padding:16}}>
                <div style={{fontSize:10, color:"#fff", fontWeight:700, marginBottom:8}}>
                  Generated Spec: {domain.name} × {tpl.name} × {theme.name}
                </div>
                <pre style={{fontSize:8, color:"#777", lineHeight:1.7, whiteSpace:"pre-wrap", fontFamily:"inherit"}}>{JSON.stringify({
                  template: tpl.id,
                  domain: selectedDomain,
                  theme: selectedTheme,
                  primitives: tpl.primitives,
                  panel_config: tpl.panel_config,
                  list_card_binding: domain.list_item_anatomy,
                  detail_sections: domain.detail_sections,
                  posture_strip: tpl.posture_strip_config || LAYOUT_PRIMITIVES.posture_strip.domain_examples[selectedDomain] || LAYOUT_PRIMITIVES.posture_strip.domain_examples.security,
                  filters: tpl.filter_config || LAYOUT_PRIMITIVES.filter_bar.domain_examples[selectedDomain] || LAYOUT_PRIMITIVES.filter_bar.domain_examples.security,
                  chat_focus: domain.chat_system_prompt_focus,
                  theme_tokens: theme.vars,
                  fonts: theme.fonts,
                }, null, 2)}</pre>
              </div>

              <div>
                <div style={{fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Live Preview</div>
                <PanelPreview
                  theme={selectedTheme}
                  strip={tpl.primitives.includes("posture_strip") ?
                    (tpl.posture_strip_config?.cells || LAYOUT_PRIMITIVES.posture_strip.domain_examples[selectedDomain] || ["Score","KPI 2","KPI 3","KPI 4","KPI 5","KPI 6"]).slice(0,6).map((c,i)=>({
                      v: i===0?"84%":i===1?"12":i===2?"3":i===3?"1":i===4?"91%":"14d", l: c
                    })) : null
                  }
                  left={{
                    title: domain.list_item_anatomy.badge.split("|")[0],
                    items: selectedDomain==="cornerstone"?["HIPAA Annual","Security Awareness","Data Privacy","Compliance 101"]:
                           selectedDomain==="workday"?["Sr. Engineer","HR Manager","Data Analyst","VP Sales"]:
                           selectedDomain==="hybrid"?["Cert Expiry","Deprov Lag","SCIM Failure","Training Gap"]:
                           ["CC7.2 Monitoring","CC6.2 Access","CC3.1 Risk","CC7.1 Vuln"],
                    badges: selectedDomain==="cornerstone"?["OVR","IP","COM","NS"]:
                            selectedDomain==="workday"?["OPN","REV","OPN","CLS"]:
                            selectedDomain==="hybrid"?["CRT","DEG","DEG","PAS"]:
                            ["F","W","W","W"]
                  }}
                  center={{
                    title: "Detail",
                    signals: selectedDomain==="cornerstone"?["completion_rate","days_overdue","cert_status"]:
                             selectedDomain==="workday"?["time_to_hire","approval_lag","headcount_delta"]:
                             selectedDomain==="hybrid"?["cert_expiry","scim_health","access_review"]:
                             ["siem_alert_sla","ioc_matched","veto_gate"],
                    graph: tpl.panel_config.center?.includes("causal_graph_svg")
                  }}
                  right={tpl.panel_config.right ? {title:"AI Advisor"} : null}
                />

                <div style={{marginTop:12, fontSize:8, color:"#555", textTransform:"uppercase", letterSpacing:".1em", marginBottom:6}}>Rendering Primitives</div>
                <div style={{display:"flex", flexDirection:"column", gap:3}}>
                  {tpl.primitives.map((p,i)=>(
                    <div key={i} style={{display:"flex", alignItems:"center", gap:6}}>
                      <span style={{fontSize:8, color:"#3b82f6", width:10}}>{i+1}</span>
                      <span style={{fontSize:8, color:"#aaa"}}>{p}</span>
                      <span style={{fontSize:7, color:"#444"}}>→ {LAYOUT_PRIMITIVES[p]?.category}</span>
                    </div>
                  ))}
                  {Object.entries(tpl.panel_config).map(([panel, comps])=>
                    comps.map((c,i)=>(
                      <div key={`${panel}-${i}`} style={{display:"flex", alignItems:"center", gap:6, marginLeft:16}}>
                        <span style={{fontSize:7, color:"#f97316"}}>{panel}</span>
                        <span style={{fontSize:8, color:"#888"}}>{c}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
