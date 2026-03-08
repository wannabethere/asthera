"""
ECharts Intent Spec — Chart Catalog
=====================================
Complete catalog of all chart types with:
  - Intent spec templates (what LLMs generate)
  - Required vs optional encodings
  - Coordinate system requirements
  - Example specs for each type
  - Embedding text for vector store retrieval

This catalog is the "knowledge base" that LLMs search to find
the right chart structure for a given data + analytical intent.

Store these in ChromaDB / FAISS / JSON for retrieval-augmented generation.
"""

from __future__ import annotations

CHART_CATALOG: dict[str, dict] = {

    # ══════════════════════════════════════════════════════════════════
    # CARTESIAN: LINE / AREA
    # ══════════════════════════════════════════════════════════════════

    "line_basic": {
        "id": "line_basic",
        "name": "Line Chart",
        "family": "line",
        "intent": ["trend_over_time"],
        "coordinate": "cartesian2d",
        "description": "Shows how a metric changes over time. Single or multi-series trend lines.",
        "when_to_use": "Time-series data where you want to see trends, patterns, or rate of change.",
        "encoding_required": {
            "x": {"type": "time|category", "description": "Time or sequential dimension"},
            "y": {"type": "measure", "min": 1, "description": "One or more numeric metrics"},
        },
        "encoding_optional": {
            "series": "Dimension to split into multiple lines",
            "color": "Categorical or continuous color mapping",
        },
        "visual_options": {
            "smooth": "bool — Bezier curve smoothing",
            "show_area": "bool — Fill area under line",
            "stack": "none|stacked|percent — Stack mode",
        },
        "example_spec": {
            "version": "eps/1.0",
            "title": "Risk Score Over Time by Department",
            "intent": "trend_over_time",
            "dataset": {"source": "ref", "ref": "risk_timeseries_gold", "time_field": "date"},
            "encoding": {
                "x": {"field": "date", "type": "time", "time_grain": "month"},
                "y": [{"field": "risk_score", "aggregate": "avg", "axis": "left"}],
                "series": {"field": "department"},
            },
            "visual": {
                "chart_family": "line",
                "coordinate": "cartesian2d",
                "orientation": "vertical",
                "stack": "none",
                "smooth": True,
                "show_area": False,
            },
            "interactions": {"tooltip": "axis", "legend": True, "data_zoom": True},
        },
    },

    "area_stacked": {
        "id": "area_stacked",
        "name": "Stacked Area Chart",
        "family": "area",
        "intent": ["trend_over_time", "composition"],
        "coordinate": "cartesian2d",
        "description": "Area chart with stacking to show composition over time. Each series stacks on top of the previous.",
        "when_to_use": "Time-series where you want to see both individual trends and cumulative total.",
        "encoding_required": {
            "x": {"type": "time|category"},
            "y": {"type": "measure", "min": 1},
        },
        "encoding_optional": {"series": "Grouping dimension for stacks"},
        "visual_options": {
            "stack": "stacked|percent",
            "smooth": "bool",
            "gradient": "bool — gradient fill",
        },
        "example_spec": {
            "version": "eps/1.0",
            "title": "Training Hours by Category Over Time",
            "intent": "composition",
            "encoding": {
                "x": {"field": "month", "type": "time", "time_grain": "month"},
                "y": [{"field": "hours", "aggregate": "sum"}],
                "series": {"field": "training_category"},
            },
            "visual": {"chart_family": "area", "stack": "stacked", "smooth": True, "show_area": True},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # CARTESIAN: BAR
    # ══════════════════════════════════════════════════════════════════

    "bar_vertical": {
        "id": "bar_vertical",
        "name": "Vertical Bar Chart",
        "family": "bar",
        "intent": ["compare_categories", "ranking"],
        "coordinate": "cartesian2d",
        "description": "Vertical bars comparing values across categories. Supports grouping and stacking.",
        "when_to_use": "Comparing discrete categories. Best when category count ≤ 12.",
        "encoding_required": {
            "x": {"type": "category", "description": "Categorical dimension"},
            "y": {"type": "measure", "min": 1},
        },
        "encoding_optional": {
            "series": "Dimension for grouped/stacked bars",
            "color": "Custom color mapping",
        },
        "visual_options": {
            "stack": "none|stacked|percent",
            "orientation": "vertical (default)",
            "bar_width": "string — e.g. '60%'",
            "border_radius": "int — rounded corners",
            "show_labels": "bool — show value labels on bars",
        },
        "example_spec": {
            "version": "eps/1.0",
            "title": "Completed Trainings by Organization — Top 10",
            "intent": "compare_categories",
            "encoding": {
                "x": {"field": "organization", "type": "category", "sort": "desc"},
                "y": [{"field": "completed_count", "aggregate": "sum"}],
            },
            "visual": {
                "chart_family": "bar",
                "orientation": "vertical",
                "stack": "none",
                "show_labels": True,
                "bar_width": "60%",
            },
        },
    },

    "bar_horizontal": {
        "id": "bar_horizontal",
        "name": "Horizontal Bar Chart",
        "family": "bar",
        "intent": ["compare_categories", "ranking"],
        "coordinate": "cartesian2d",
        "description": "Horizontal bars — ideal for long category labels and ranking displays.",
        "when_to_use": "When category names are long or you have many categories (10+). Natural for ranked lists.",
        "encoding_required": {
            "x": {"type": "measure"},
            "y": {"type": "category", "description": "Categorical dimension on y-axis for horizontal"},
        },
        "encoding_optional": {"series": "Grouping dimension"},
        "visual_options": {"orientation": "horizontal", "show_labels": "bool"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Learners by Job Role",
            "intent": "ranking",
            "encoding": {
                "x": {"field": "job_role", "type": "category"},
                "y": [{"field": "learner_count", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "bar", "orientation": "horizontal", "show_labels": True},
        },
    },

    "bar_grouped": {
        "id": "bar_grouped",
        "name": "Grouped Bar Chart",
        "family": "bar",
        "intent": ["compare_categories"],
        "coordinate": "cartesian2d",
        "description": "Side-by-side bars for comparing multiple measures across categories.",
        "when_to_use": "When comparing 2-4 measures across categories simultaneously.",
        "encoding_required": {
            "x": {"type": "category"},
            "y": {"type": "measure", "min": 2, "description": "Multiple measures displayed as grouped bars"},
        },
        "encoding_optional": {},
        "visual_options": {"bar_gap": "string — gap between groups"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Assigned vs Completed Trainings by Department",
            "intent": "compare_categories",
            "encoding": {
                "x": {"field": "department", "type": "category"},
                "y": [
                    {"field": "assigned_count", "aggregate": "sum", "label": "Assigned"},
                    {"field": "completed_count", "aggregate": "sum", "label": "Completed"},
                ],
            },
            "visual": {"chart_family": "bar", "stack": "none"},
        },
    },

    "bar_stacked": {
        "id": "bar_stacked",
        "name": "Stacked Bar Chart",
        "family": "bar",
        "intent": ["compare_categories", "composition"],
        "coordinate": "cartesian2d",
        "description": "Stacked bars showing both individual and total values per category.",
        "when_to_use": "When you need to show part-to-whole within each category.",
        "encoding_required": {
            "x": {"type": "category"},
            "y": {"type": "measure", "min": 1},
        },
        "encoding_optional": {"series": "Grouping dimension for stacks"},
        "visual_options": {"stack": "stacked|percent"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Training Status by Department",
            "intent": "composition",
            "encoding": {
                "x": {"field": "department", "type": "category"},
                "y": [{"field": "count", "aggregate": "sum"}],
                "series": {"field": "status"},
            },
            "visual": {"chart_family": "bar", "stack": "stacked"},
        },
    },

    "bar_waterfall": {
        "id": "bar_waterfall",
        "name": "Waterfall Chart",
        "family": "waterfall",
        "intent": ["deviation", "composition"],
        "coordinate": "cartesian2d",
        "description": "Shows cumulative effect of sequential positive/negative values. Running total with increments/decrements.",
        "when_to_use": "Financial analysis, showing how individual changes add up to a total.",
        "encoding_required": {
            "x": {"type": "category", "description": "Sequential steps/categories"},
            "y": {"type": "measure", "min": 1, "description": "Increment/decrement value"},
        },
        "encoding_optional": {},
        "visual_options": {"show_labels": "bool"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Risk Score Changes: Q1 → Q4",
            "intent": "deviation",
            "encoding": {
                "x": {"field": "factor", "type": "category"},
                "y": [{"field": "delta", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "waterfall", "show_labels": True},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # CARTESIAN: SCATTER / BUBBLE
    # ══════════════════════════════════════════════════════════════════

    "scatter_basic": {
        "id": "scatter_basic",
        "name": "Scatter Plot",
        "family": "scatter",
        "intent": ["relationship", "correlation", "distribution"],
        "coordinate": "cartesian2d",
        "description": "Plots two numeric variables against each other to reveal relationships.",
        "when_to_use": "When exploring correlation, clusters, or outliers between two metrics.",
        "encoding_required": {
            "x": {"type": "value", "description": "First numeric variable"},
            "y": {"type": "measure", "min": 1, "description": "Second numeric variable"},
        },
        "encoding_optional": {
            "series": "Categorical grouping",
            "size": "Third numeric variable mapped to point size (bubble chart)",
            "color": "Categorical or continuous color",
        },
        "visual_options": {"symbol_size": "int — default point size"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "CVSS Score vs Remediation Time",
            "intent": "relationship",
            "encoding": {
                "x": {"field": "cvss_score", "type": "value"},
                "y": [{"field": "remediation_days", "aggregate": "none"}],
                "series": {"field": "severity"},
                "size": {"field": "affected_assets", "min_size": 4, "max_size": 40},
            },
            "visual": {"chart_family": "scatter", "symbol_size": 10},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # CARTESIAN: HEATMAP
    # ══════════════════════════════════════════════════════════════════

    "heatmap": {
        "id": "heatmap",
        "name": "Heatmap",
        "family": "heatmap",
        "intent": ["relationship", "distribution"],
        "coordinate": "cartesian2d",
        "description": "Color-coded matrix showing magnitude across two dimensions. Cells colored by value intensity.",
        "when_to_use": "Two categorical dimensions with a numeric value per cell. Risk matrices, correlation tables, time-of-day patterns.",
        "encoding_required": {
            "x": {"type": "category", "description": "Column dimension"},
            "y": {"type": "category", "description": "Row dimension"},
            "color": {"type": "measure", "description": "Value that determines cell color intensity"},
        },
        "encoding_optional": {},
        "visual_options": {"palette": "string — sequential color palette"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Risk Heatmap: Likelihood vs Impact",
            "intent": "relationship",
            "encoding": {
                "x": {"field": "likelihood", "type": "category"},
                "y": [{"field": "impact", "aggregate": "none"}],
                "color": {"field": "risk_count", "type": "measure"},
            },
            "visual": {"chart_family": "heatmap"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # CARTESIAN: BOXPLOT
    # ══════════════════════════════════════════════════════════════════

    "boxplot": {
        "id": "boxplot",
        "name": "Box Plot",
        "family": "boxplot",
        "intent": ["distribution"],
        "coordinate": "cartesian2d",
        "description": "Shows statistical distribution — median, quartiles, and outliers per category.",
        "when_to_use": "Comparing distributions across groups. Identifying outliers, skew, and spread.",
        "encoding_required": {
            "x": {"type": "category", "description": "Grouping dimension"},
            "y": {"type": "measure", "min": 1, "description": "Numeric values to compute box statistics"},
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Score Distribution by Training Type",
            "intent": "distribution",
            "encoding": {
                "x": {"field": "training_type", "type": "category"},
                "y": [{"field": "score", "aggregate": "none"}],
            },
            "visual": {"chart_family": "boxplot"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # CARTESIAN: CANDLESTICK
    # ══════════════════════════════════════════════════════════════════

    "candlestick": {
        "id": "candlestick",
        "name": "Candlestick Chart",
        "family": "candlestick",
        "intent": ["trend_over_time"],
        "coordinate": "cartesian2d",
        "description": "Shows open-high-low-close values over time. Each candle represents a time period.",
        "when_to_use": "Financial data, or any metric with open/high/low/close semantics per period.",
        "encoding_required": {
            "x": {"type": "time", "description": "Time dimension"},
            "y": {"type": "measure", "min": 4, "description": "open, close, low, high fields"},
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Risk Score OHLC — Weekly",
            "intent": "trend_over_time",
            "encoding": {
                "x": {"field": "week", "type": "time", "time_grain": "week"},
                "y": [
                    {"field": "open", "aggregate": "none", "label": "Open"},
                    {"field": "close", "aggregate": "none", "label": "Close"},
                    {"field": "low", "aggregate": "none", "label": "Low"},
                    {"field": "high", "aggregate": "none", "label": "High"},
                ],
            },
            "visual": {"chart_family": "candlestick"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # POLAR / RADIAL
    # ══════════════════════════════════════════════════════════════════

    "pie": {
        "id": "pie",
        "name": "Pie Chart",
        "family": "pie",
        "intent": ["part_to_whole", "composition"],
        "coordinate": "none",
        "description": "Circular chart divided into slices proportional to values. Best with ≤7 slices.",
        "when_to_use": "Showing proportion/share of a total. Limit to 5-7 categories max.",
        "encoding_required": {
            "x": {"type": "category", "description": "Slice label (dimension)"},
            "y": {"type": "measure", "min": 1, "description": "Slice value"},
        },
        "encoding_optional": {},
        "visual_options": {
            "inner_radius": "string — '0%' for pie, '40%' for donut",
            "rose_type": "'radius' or 'area' for nightingale rose chart",
            "show_labels": "bool — show labels on slices",
        },
        "example_spec": {
            "version": "eps/1.0",
            "title": "Training Hours by Age Category",
            "intent": "part_to_whole",
            "encoding": {
                "x": {"field": "age_category", "type": "category"},
                "y": [{"field": "hours", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "pie", "show_labels": True},
        },
    },

    "donut": {
        "id": "donut",
        "name": "Donut Chart",
        "family": "donut",
        "intent": ["part_to_whole", "composition"],
        "coordinate": "none",
        "description": "Pie chart with a hollow center — room for a center label or KPI. Feels cleaner than pie.",
        "when_to_use": "Same as pie but when you want a center metric or cleaner visual. Common for compliance %.",
        "encoding_required": {
            "x": {"type": "category"},
            "y": {"type": "measure", "min": 1},
        },
        "encoding_optional": {"label_field": "Center label text"},
        "visual_options": {"inner_radius": "'40%'—'60%'"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Assigned Training Compliance",
            "intent": "part_to_whole",
            "encoding": {
                "x": {"field": "status", "type": "category"},
                "y": [{"field": "count", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "donut", "inner_radius": "45%", "outer_radius": "70%", "show_labels": True},
        },
    },

    "radar": {
        "id": "radar",
        "name": "Radar / Spider Chart",
        "family": "radar",
        "intent": ["compare_categories", "distribution"],
        "coordinate": "polar",
        "description": "Multi-axis radial chart comparing multiple dimensions simultaneously. Each spoke is a metric.",
        "when_to_use": "Comparing entities across 3-8 balanced dimensions. Framework posture, balanced scorecard.",
        "encoding_required": {
            "x": {"type": "category", "description": "Spoke labels (dimensions to compare)"},
            "y": {"type": "measure", "min": 1, "description": "Values for each spoke"},
        },
        "encoding_optional": {"series": "Multiple entities to overlay"},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "SOC2 Framework Posture — CC Families",
            "intent": "compare_categories",
            "encoding": {
                "x": {"field": "cc_family", "type": "category"},
                "y": [{"field": "posture_score", "aggregate": "avg"}],
                "series": {"field": "quarter"},
            },
            "visual": {"chart_family": "radar", "coordinate": "polar"},
        },
    },

    "gauge": {
        "id": "gauge",
        "name": "Gauge Chart",
        "family": "gauge",
        "intent": ["status_kpi"],
        "coordinate": "none",
        "description": "Speedometer-style display showing a single metric against a scale. Strong visual impact for KPIs.",
        "when_to_use": "Single KPI with a known range and thresholds (good/warn/critical).",
        "encoding_required": {
            "y": {"type": "measure", "min": 1, "description": "Single metric value"},
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Overall Compliance Posture",
            "intent": "status_kpi",
            "encoding": {
                "y": [{"field": "posture_score", "aggregate": "avg", "label": "Score"}],
            },
            "visual": {"chart_family": "gauge"},
            "semantics": {
                "unit": "score_0_100",
                "good_direction": "up",
                "thresholds": {"critical": 60, "warning": 80, "good": 90},
            },
        },
    },

    "funnel": {
        "id": "funnel",
        "name": "Funnel Chart",
        "family": "funnel",
        "intent": ["composition", "flow"],
        "coordinate": "none",
        "description": "Tapered stages showing progressive reduction. Each stage narrower than the last.",
        "when_to_use": "Sequential process stages with drop-off: sales funnel, onboarding stages, training pipeline.",
        "encoding_required": {
            "x": {"type": "category", "description": "Stage names"},
            "y": {"type": "measure", "min": 1, "description": "Value per stage"},
        },
        "encoding_optional": {},
        "visual_options": {"orientation": "vertical|horizontal", "sort": "desc|asc|none"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Onboarding Pipeline",
            "intent": "flow",
            "encoding": {
                "x": {"field": "stage", "type": "category"},
                "y": [{"field": "employee_count", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "funnel"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # HIERARCHICAL
    # ══════════════════════════════════════════════════════════════════

    "treemap": {
        "id": "treemap",
        "name": "Treemap",
        "family": "treemap",
        "intent": ["hierarchy", "part_to_whole"],
        "coordinate": "none",
        "description": "Nested rectangles sized by value. Shows hierarchical data with part-to-whole proportions.",
        "when_to_use": "Hierarchical data where size matters: storage usage, budget breakdown, org training hours.",
        "encoding_required": {
            "value_field": "Numeric value that determines rectangle size",
        },
        "encoding_optional": {
            "parent_field": "Parent reference for flat data",
            "children_field": "Nested children array",
            "color": "Color by measure or category",
        },
        "visual_options": {"show_labels": "bool"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Training Hours by Org > Department",
            "intent": "hierarchy",
            "encoding": {
                "value_field": "total_hours",
                "parent_field": "parent_org",
                "x": {"field": "name", "type": "category"},
                "y": [{"field": "total_hours", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "treemap"},
        },
    },

    "sunburst": {
        "id": "sunburst",
        "name": "Sunburst Chart",
        "family": "sunburst",
        "intent": ["hierarchy", "part_to_whole"],
        "coordinate": "none",
        "description": "Radial treemap — concentric rings represent hierarchy levels. Inner ring = top level.",
        "when_to_use": "Multi-level hierarchy where you want to see proportions at each level.",
        "encoding_required": {
            "value_field": "Numeric value for segment size",
        },
        "encoding_optional": {"children_field": "Nested children"},
        "visual_options": {"inner_radius": "string", "outer_radius": "string"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Control Family > Control > Evidence Breakdown",
            "intent": "hierarchy",
            "encoding": {
                "value_field": "evidence_count",
                "children_field": "children",
                "x": {"field": "name", "type": "category"},
                "y": [{"field": "evidence_count", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "sunburst"},
        },
    },

    "tree": {
        "id": "tree",
        "name": "Tree Diagram",
        "family": "tree",
        "intent": ["hierarchy"],
        "coordinate": "none",
        "description": "Node-link tree showing parent-child relationships. Expandable/collapsible.",
        "when_to_use": "Organizational structures, taxonomy, classification hierarchies.",
        "encoding_required": {
            "children_field": "Nested children array",
        },
        "encoding_optional": {"value_field": "Node size/weight"},
        "visual_options": {"orientation": "vertical|horizontal|radial"},
        "example_spec": {
            "version": "eps/1.0",
            "title": "SOC2 Control Hierarchy",
            "intent": "hierarchy",
            "encoding": {
                "children_field": "children",
                "x": {"field": "name", "type": "category"},
                "y": [{"field": "score", "aggregate": "none"}],
            },
            "visual": {"chart_family": "tree", "orientation": "horizontal"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # RELATIONAL / FLOW
    # ══════════════════════════════════════════════════════════════════

    "sankey": {
        "id": "sankey",
        "name": "Sankey Diagram",
        "family": "sankey",
        "intent": ["flow"],
        "coordinate": "none",
        "description": "Flow diagram showing quantities between stages/nodes. Width of links proportional to value.",
        "when_to_use": "Showing flow of resources, risk propagation, data lineage, budget allocation between categories.",
        "encoding_required": {
            "source_field": "Source node field",
            "target_field": "Target node field",
            "value_field": "Flow weight / quantity",
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Risk Flow: Control Failures → Incident Types",
            "intent": "flow",
            "encoding": {
                "source_field": "source_control",
                "target_field": "incident_type",
                "value_field": "incident_count",
                "x": {"field": "source_control", "type": "category"},
                "y": [{"field": "incident_count", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "sankey", "coordinate": "none"},
        },
    },

    "graph": {
        "id": "graph",
        "name": "Force-Directed Graph",
        "family": "graph",
        "intent": ["relationship", "flow"],
        "coordinate": "none",
        "description": "Network graph with nodes and edges. Force-directed layout positions related nodes closer together.",
        "when_to_use": "Entity relationships, attack graphs, dependency networks, knowledge graphs.",
        "encoding_required": {
            "source_field": "Edge source node",
            "target_field": "Edge target node",
        },
        "encoding_optional": {
            "value_field": "Edge weight",
            "size": "Node size by measure",
            "color": "Node category color",
        },
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Asset-Vulnerability Relationship Graph",
            "intent": "relationship",
            "encoding": {
                "source_field": "asset",
                "target_field": "cve_id",
                "value_field": "severity_score",
                "x": {"field": "asset", "type": "category"},
                "y": [{"field": "severity_score", "aggregate": "none"}],
            },
            "visual": {"chart_family": "graph"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # SPECIALIZED
    # ══════════════════════════════════════════════════════════════════

    "parallel": {
        "id": "parallel",
        "name": "Parallel Coordinates",
        "family": "parallel",
        "intent": ["comparison", "distribution"],
        "coordinate": "parallel",
        "description": "Multiple parallel vertical axes — each row is a line crossing all axes. Reveals patterns across many dimensions.",
        "when_to_use": "Comparing entities across many numeric dimensions simultaneously (5+).",
        "encoding_required": {
            "y": {"type": "measure", "min": 3, "description": "Multiple numeric dimensions as parallel axes"},
        },
        "encoding_optional": {"series": "Categorical grouping for line coloring"},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Vendor Risk Profile Comparison",
            "intent": "compare_categories",
            "encoding": {
                "x": {"field": "vendor_name", "type": "category"},
                "y": [
                    {"field": "security_score", "aggregate": "none", "label": "Security"},
                    {"field": "compliance_score", "aggregate": "none", "label": "Compliance"},
                    {"field": "financial_score", "aggregate": "none", "label": "Financial"},
                    {"field": "operational_score", "aggregate": "none", "label": "Operational"},
                ],
            },
            "visual": {"chart_family": "parallel", "coordinate": "parallel"},
        },
    },

    "theme_river": {
        "id": "theme_river",
        "name": "Theme River",
        "family": "theme_river",
        "intent": ["trend_over_time", "composition"],
        "coordinate": "single",
        "description": "Streamgraph showing thematic volumes over time. Rivers widen/narrow based on value. Centered around baseline.",
        "when_to_use": "Showing how multiple categories' volumes evolve over time with flowing visual.",
        "encoding_required": {
            "x": {"type": "time"},
            "y": {"type": "measure", "min": 1},
            "series": "Category field for each river stream",
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Training Volume by Category Over Time",
            "intent": "composition",
            "encoding": {
                "x": {"field": "date", "type": "time"},
                "y": [{"field": "enrollment_count", "aggregate": "sum"}],
                "series": {"field": "category"},
            },
            "visual": {"chart_family": "theme_river", "coordinate": "single"},
        },
    },

    "pictorial_bar": {
        "id": "pictorial_bar",
        "name": "Pictorial Bar",
        "family": "pictorial_bar",
        "intent": ["compare_categories"],
        "coordinate": "cartesian2d",
        "description": "Bar chart where bars are filled with SVG symbols/icons for infographic style.",
        "when_to_use": "Infographic / executive presentation style. 3-6 categories max.",
        "encoding_required": {
            "x": {"type": "category"},
            "y": {"type": "measure", "min": 1},
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Training Completions by Region",
            "intent": "compare_categories",
            "encoding": {
                "x": {"field": "region", "type": "category"},
                "y": [{"field": "completions", "aggregate": "sum"}],
            },
            "visual": {"chart_family": "pictorial_bar"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # GEO
    # ══════════════════════════════════════════════════════════════════

    "geo_map": {
        "id": "geo_map",
        "name": "Geographic Map",
        "family": "map",
        "intent": ["geo"],
        "coordinate": "geo",
        "description": "Choropleth or bubble map showing geographic distribution of metrics.",
        "when_to_use": "When data has geographic context — regional sales, global compliance posture, office locations.",
        "encoding_required": {
            "region_field": "Geographic region name or code (country, state)",
        },
        "encoding_optional": {
            "lat_field": "Latitude for point overlays",
            "lng_field": "Longitude for point overlays",
            "value_field": "Metric for color intensity / bubble size",
        },
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Compliance Posture by Region",
            "intent": "geo",
            "encoding": {
                "region_field": "country",
                "x": {"field": "country", "type": "category"},
                "y": [{"field": "posture_score", "aggregate": "avg"}],
            },
            "visual": {"chart_family": "map", "coordinate": "geo"},
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # COMPOSITE / COMBO
    # ══════════════════════════════════════════════════════════════════

    "dual_axis": {
        "id": "dual_axis",
        "name": "Dual-Axis Chart",
        "family": "dual_axis",
        "intent": ["trend_over_time", "compare_categories", "correlation"],
        "coordinate": "cartesian2d",
        "description": "Two y-axes (left + right) showing different metrics on the same x-axis. Typically line + bar.",
        "when_to_use": "When comparing two metrics with different scales on the same time/category axis.",
        "encoding_required": {
            "x": {"type": "time|category"},
            "y": {"type": "measure", "min": 2, "description": "Two measures — one per axis"},
        },
        "encoding_optional": {},
        "visual_options": {},
        "charts_pattern": [
            {"type": "bar", "y_field": "measure_1", "axis_index": 0},
            {"type": "line", "y_field": "measure_2", "axis_index": 1},
        ],
        "example_spec": {
            "version": "eps/1.0",
            "title": "YOY Activity Launches vs Completions",
            "intent": "trend_over_time",
            "encoding": {
                "x": {"field": "year", "type": "category"},
                "y": [
                    {"field": "launches", "aggregate": "sum", "axis": "left", "label": "Launches"},
                    {"field": "completions", "aggregate": "sum", "axis": "right", "label": "Completions"},
                ],
            },
            "visual": {"chart_family": "dual_axis"},
            "charts": [
                {"id": "c1", "coordinate": "cartesian2d", "series": [
                    {"type": "bar", "y_field": "launches", "axis_index": 0},
                    {"type": "line", "y_field": "completions", "axis_index": 1},
                ]},
            ],
        },
    },

    "combo": {
        "id": "combo",
        "name": "Combo Chart (Bar + Line)",
        "family": "combo",
        "intent": ["trend_over_time", "compare_categories"],
        "coordinate": "cartesian2d",
        "description": "Multiple chart types on the same axes — commonly bar + line overlaid.",
        "when_to_use": "When you need to show a categorical comparison (bar) alongside a trend (line) on the same chart.",
        "encoding_required": {
            "x": {"type": "time|category"},
            "y": {"type": "measure", "min": 2},
        },
        "encoding_optional": {},
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Monthly Training Hours (Bar) + Completion Rate (Line)",
            "intent": "trend_over_time",
            "encoding": {
                "x": {"field": "month", "type": "time", "time_grain": "month"},
                "y": [
                    {"field": "total_hours", "aggregate": "sum", "label": "Hours"},
                    {"field": "completion_rate", "aggregate": "avg", "axis": "right", "label": "Completion %"},
                ],
            },
            "visual": {"chart_family": "combo"},
            "charts": [
                {"id": "c1", "coordinate": "cartesian2d", "series": [
                    {"type": "bar", "y_field": "total_hours", "axis_index": 0},
                    {"type": "line", "y_field": "completion_rate", "axis_index": 1, "smooth": True},
                ]},
            ],
        },
    },

    # ══════════════════════════════════════════════════════════════════
    # KPI
    # ══════════════════════════════════════════════════════════════════

    "kpi_card": {
        "id": "kpi_card",
        "name": "KPI Card / Status Indicator",
        "family": "kpi_card",
        "intent": ["status_kpi"],
        "coordinate": "none",
        "description": "Single large metric with optional delta, sparkline, and status color. Not a traditional chart.",
        "when_to_use": "Dashboard header KPIs, scorecard cells, at-a-glance metrics.",
        "encoding_required": {
            "y": {"type": "measure", "min": 1, "description": "Primary metric value"},
        },
        "encoding_optional": {
            "label_field": "KPI label",
            "tooltip_fields": "Breakdown fields in tooltip",
        },
        "visual_options": {},
        "example_spec": {
            "version": "eps/1.0",
            "title": "Overall Posture Score",
            "intent": "status_kpi",
            "encoding": {
                "y": [{"field": "posture_score", "aggregate": "avg", "format": ".0f", "label": "Posture"}],
            },
            "visual": {"chart_family": "kpi_card"},
            "semantics": {
                "unit": "score_0_100",
                "good_direction": "up",
                "thresholds": {"critical": 60, "warning": 80, "good": 90},
            },
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════
# CATALOG HELPERS
# ═══════════════════════════════════════════════════════════════════════

def get_chart_by_family(family: str) -> list[dict]:
    """Get all chart definitions for a given family."""
    return [c for c in CHART_CATALOG.values() if c["family"] == family]


def get_charts_by_intent(intent: str) -> list[dict]:
    """Get all chart types that serve a given intent."""
    return [c for c in CHART_CATALOG.values() if intent in c["intent"]]


def get_chart_families() -> list[str]:
    """Get unique chart families."""
    return sorted(set(c["family"] for c in CHART_CATALOG.values()))


def get_catalog_embedding_text(chart: dict) -> str:
    """Build embedding text for vector store ingestion."""
    parts = [
        chart["name"],
        chart["description"],
        f"Chart family: {chart['family']}",
        f"Intent: {', '.join(chart['intent'])}",
        f"Coordinate system: {chart['coordinate']}",
        f"When to use: {chart['when_to_use']}",
        f"Required encodings: {', '.join(chart['encoding_required'].keys())}",
    ]
    if chart.get("encoding_optional"):
        parts.append(f"Optional encodings: {', '.join(chart['encoding_optional'].keys())}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# INTENT → CHART MAPPING (for LLM prompt guidance)
# ═══════════════════════════════════════════════════════════════════════

INTENT_CHART_MAP: dict[str, list[str]] = {
    "trend_over_time":      ["line_basic", "area_stacked", "bar_vertical", "dual_axis", "combo", "candlestick", "theme_river"],
    "compare_categories":   ["bar_vertical", "bar_horizontal", "bar_grouped", "bar_stacked", "radar", "pictorial_bar", "parallel"],
    "distribution":         ["scatter_basic", "boxplot", "heatmap"],
    "relationship":         ["scatter_basic", "heatmap", "graph"],
    "correlation":          ["scatter_basic", "dual_axis"],
    "part_to_whole":        ["pie", "donut", "treemap", "sunburst"],
    "ranking":              ["bar_horizontal", "bar_vertical"],
    "composition":          ["area_stacked", "bar_stacked", "pie", "donut", "bar_waterfall", "theme_river"],
    "deviation":            ["bar_waterfall"],
    "flow":                 ["sankey", "funnel"],
    "hierarchy":            ["treemap", "sunburst", "tree"],
    "geo":                  ["geo_map"],
    "status_kpi":           ["gauge", "kpi_card"],
    "table":                [],
}
