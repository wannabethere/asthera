# Risk Analytics Visualization Guide

## Complete Guide to Creating Dashboards from Risk Data Marts

---

## Table of Contents
1. [Setup & Dependencies](#setup--dependencies)
2. [Risk Trend Visualizations](#risk-trend-visualizations)
3. [Survival Curve Plots](#survival-curve-plots)
4. [Cohort Analysis Heatmaps](#cohort-analysis-heatmaps)
5. [Interactive Dashboards](#interactive-dashboards)
6. [Executive Reports](#executive-reports)

---

## Setup & Dependencies

```python
# visualization_toolkit.py
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import psycopg2
from datetime import datetime, timedelta
import streamlit as st
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.plotting import plot_lifetimes

# Database connection
def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))
```

---

## Risk Trend Visualizations

### 1. Individual Risk Trajectory Plot

```python
def plot_risk_trajectory(entity_id: str, domain: str = 'Employee Attrition'):
    """
    Multi-line chart showing risk, likelihood, and impact over time
    with moving averages and intervention markers
    """
    
    query = """
    SELECT 
        dt.date_actual,
        f.overall_risk_score,
        f.likelihood_score,
        f.impact_score,
        AVG(f.overall_risk_score) OVER (
            PARTITION BY f.entity_key
            ORDER BY f.assessment_date_key
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as risk_7day_ma,
        f.risk_level
    FROM fact_risk_assessment f
    JOIN dim_entity e ON f.entity_key = e.entity_key
    JOIN dim_date dt ON f.assessment_date_key = dt.date_key
    JOIN dim_risk_domain d ON f.domain_key = d.domain_key
    WHERE e.entity_id = %s
      AND d.domain_name = %s
      AND dt.date_actual >= CURRENT_DATE - INTERVAL '90 days'
    ORDER BY dt.date_actual
    """
    
    conn = get_connection()
    df = pd.read_sql(query, conn, params=[entity_id, domain])
    conn.close()
    
    # Create figure with secondary y-axis
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.7, 0.3],
        subplot_titles=('Risk Score Trajectory', 'Risk Level'),
        vertical_spacing=0.1
    )
    
    # Main risk scores
    fig.add_trace(
        go.Scatter(
            x=df['date_actual'],
            y=df['overall_risk_score'],
            name='Overall Risk',
            line=dict(color='#E74C3C', width=2),
            mode='lines+markers'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['date_actual'],
            y=df['risk_7day_ma'],
            name='7-Day MA',
            line=dict(color='#E74C3C', width=2, dash='dash'),
            mode='lines'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['date_actual'],
            y=df['likelihood_score'],
            name='Likelihood',
            line=dict(color='#F39C12', width=1.5),
            mode='lines'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['date_actual'],
            y=df['impact_score'],
            name='Impact',
            line=dict(color='#3498DB', width=1.5),
            mode='lines'
        ),
        row=1, col=1
    )
    
    # Risk level bar chart
    risk_level_map = {'CRITICAL': 5, 'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'MINIMAL': 1}
    df['risk_level_numeric'] = df['risk_level'].map(risk_level_map)
    
    colors = df['risk_level'].map({
        'CRITICAL': '#C0392B',
        'HIGH': '#E74C3C',
        'MEDIUM': '#F39C12',
        'LOW': '#27AE60',
        'MINIMAL': '#2ECC71'
    })
    
    fig.add_trace(
        go.Bar(
            x=df['date_actual'],
            y=df['risk_level_numeric'],
            name='Risk Level',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )
    
    # Add threshold lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", 
                  annotation_text="Critical Threshold", row=1, col=1)
    fig.add_hline(y=50, line_dash="dash", line_color="orange",
                  annotation_text="High Threshold", row=1, col=1)
    
    # Layout
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Risk Score (0-100)", row=1, col=1)
    fig.update_yaxes(title_text="Level", row=2, col=1,
                     tickvals=[1, 2, 3, 4, 5],
                     ticktext=['MIN', 'LOW', 'MED', 'HIGH', 'CRIT'])
    
    fig.update_layout(
        title=f'Risk Trajectory: {entity_id} ({domain})',
        height=600,
        hovermode='x unified',
        template='plotly_white'
    )
    
    return fig


# Usage
fig = plot_risk_trajectory('USR12345', 'Employee Attrition')
fig.show()
```

---

### 2. Population Risk Distribution Over Time

```python
def plot_risk_distribution_evolution(domain: str = 'Employee Attrition'):
    """
    Stacked area chart showing evolution of risk distribution
    """
    
    query = """
    SELECT 
        dt.year_number,
        dt.month_number,
        dt.date_actual,
        d.domain_name,
        COUNT(*) FILTER (WHERE f.risk_level = 'CRITICAL') as critical,
        COUNT(*) FILTER (WHERE f.risk_level = 'HIGH') as high,
        COUNT(*) FILTER (WHERE f.risk_level = 'MEDIUM') as medium,
        COUNT(*) FILTER (WHERE f.risk_level = 'LOW') as low
    FROM fact_risk_assessment f
    JOIN dim_date dt ON f.assessment_date_key = dt.date_key
    JOIN dim_risk_domain d ON f.domain_key = d.domain_key
    WHERE d.domain_name = %s
      AND dt.is_month_end = TRUE
      AND dt.date_actual >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY dt.year_number, dt.month_number, dt.date_actual, d.domain_name
    ORDER BY dt.date_actual
    """
    
    conn = get_connection()
    df = pd.read_sql(query, conn, params=[domain])
    conn.close()
    
    # Create stacked area chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['date_actual'], y=df['low'],
        name='Low',
        mode='lines',
        stackgroup='one',
        fillcolor='#2ECC71',
        line=dict(width=0)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date_actual'], y=df['medium'],
        name='Medium',
        mode='lines',
        stackgroup='one',
        fillcolor='#F39C12',
        line=dict(width=0)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date_actual'], y=df['high'],
        name='High',
        mode='lines',
        stackgroup='one',
        fillcolor='#E74C3C',
        line=dict(width=0)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date_actual'], y=df['critical'],
        name='Critical',
        mode='lines',
        stackgroup='one',
        fillcolor='#C0392B',
        line=dict(width=0)
    ))
    
    fig.update_layout(
        title=f'Risk Distribution Evolution: {domain}',
        xaxis_title='Month',
        yaxis_title='Number of Entities',
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    
    return fig
```

---

### 3. Likelihood vs Impact Scatter Plot with Quadrants

```python
def plot_likelihood_impact_matrix(domain: str = 'Employee Attrition'):
    """
    Scatter plot showing risk quadrants
    Size = risk score, Color = risk level
    """
    
    query = """
    WITH latest_scores AS (
        SELECT DISTINCT ON (e.entity_id)
            e.entity_id,
            e.entity_name,
            f.likelihood_score,
            f.impact_score,
            f.overall_risk_score,
            f.risk_level
        FROM fact_risk_assessment f
        JOIN dim_entity e ON f.entity_key = e.entity_key
        JOIN dim_risk_domain d ON f.domain_key = d.domain_key
        WHERE d.domain_name = %s
        ORDER BY e.entity_id, f.assessment_date_key DESC
    )
    SELECT * FROM latest_scores
    """
    
    conn = get_connection()
    df = pd.read_sql(query, conn, params=[domain])
    conn.close()
    
    # Color mapping
    color_map = {
        'CRITICAL': '#C0392B',
        'HIGH': '#E74C3C',
        'MEDIUM': '#F39C12',
        'LOW': '#27AE60'
    }
    
    fig = px.scatter(
        df,
        x='likelihood_score',
        y='impact_score',
        size='overall_risk_score',
        color='risk_level',
        color_discrete_map=color_map,
        hover_data=['entity_id', 'entity_name'],
        title=f'Risk Quadrant Analysis: {domain}'
    )
    
    # Add quadrant lines
    fig.add_hline(y=70, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=70, line_dash="dash", line_color="gray", opacity=0.5)
    
    # Add quadrant annotations
    fig.add_annotation(x=85, y=85, text="High L / High I<br>URGENT ACTION",
                      showarrow=False, bgcolor="rgba(192, 57, 43, 0.2)")
    fig.add_annotation(x=85, y=35, text="High L / Low I<br>PREVENT",
                      showarrow=False, bgcolor="rgba(243, 156, 18, 0.2)")
    fig.add_annotation(x=35, y=85, text="Low L / High I<br>PREPARE",
                      showarrow=False, bgcolor="rgba(52, 152, 219, 0.2)")
    fig.add_annotation(x=35, y=35, text="Low L / Low I<br>MONITOR",
                      showarrow=False, bgcolor="rgba(46, 204, 113, 0.2)")
    
    fig.update_xaxes(title='Likelihood Score', range=[0, 100])
    fig.update_yaxes(title='Impact Score', range=[0, 100])
    fig.update_layout(template='plotly_white', height=600)
    
    return fig
```

---

## Survival Curve Plots

### 4. Kaplan-Meier Survival Curve

```python
def plot_survival_curve(domain: str = 'Employee Attrition', 
                       cohort_month: str = None,
                       compare_by: str = None):
    """
    Kaplan-Meier survival curve with confidence intervals
    Optional: Compare different groups
    """
    
    query = """
    SELECT 
        s.survival_time_days,
        s.event_occurred::INTEGER as event,
        e.entity_type,
        s.intervention_applied,
        s.risk_trend
    FROM fact_survival_events s
    JOIN dim_risk_domain d ON s.domain_key = d.domain_key
    JOIN dim_entity e ON s.entity_key = e.entity_key
    WHERE d.domain_name = %s
    """
    
    params = [domain]
    if cohort_month:
        query += " AND s.cohort_month = %s"
        params.append(cohort_month)
    
    conn = get_connection()
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    
    fig = go.Figure()
    
    if compare_by and compare_by in df.columns:
        # Plot separate curves for each group
        for group in df[compare_by].unique():
            group_data = df[df[compare_by] == group]
            
            kmf = KaplanMeierFitter()
            kmf.fit(
                durations=group_data['survival_time_days'],
                event_observed=group_data['event'],
                label=str(group)
            )
            
            # Survival function
            sf = kmf.survival_function_
            ci = kmf.confidence_interval_survival_function_
            
            fig.add_trace(go.Scatter(
                x=sf.index,
                y=sf.iloc[:, 0],
                name=str(group),
                mode='lines',
                line=dict(width=2)
            ))
            
            # Confidence interval
            fig.add_trace(go.Scatter(
                x=sf.index.tolist() + sf.index.tolist()[::-1],
                y=ci.iloc[:, 0].tolist() + ci.iloc[:, 1].tolist()[::-1],
                fill='toself',
                fillcolor='rgba(0,100,200,0.1)',
                line=dict(color='rgba(255,255,255,0)'),
                showlegend=False,
                name=f'{group} CI'
            ))
    else:
        # Single curve
        kmf = KaplanMeierFitter()
        kmf.fit(
            durations=df['survival_time_days'],
            event_observed=df['event']
        )
        
        sf = kmf.survival_function_
        ci = kmf.confidence_interval_survival_function_
        
        fig.add_trace(go.Scatter(
            x=sf.index,
            y=sf.iloc[:, 0],
            name='Survival Probability',
            mode='lines',
            line=dict(color='#3498DB', width=3)
        ))
        
        # Confidence interval
        fig.add_trace(go.Scatter(
            x=sf.index.tolist() + sf.index.tolist()[::-1],
            y=ci.iloc[:, 0].tolist() + ci.iloc[:, 1].tolist()[::-1],
            fill='toself',
            fillcolor='rgba(52, 152, 219, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            showlegend=False,
            name='95% CI'
        ))
        
        # Add median survival line
        median_survival = kmf.median_survival_time_
        fig.add_hline(y=0.5, line_dash="dash", line_color="red",
                     annotation_text=f"Median: {median_survival:.0f} days")
    
    fig.update_layout(
        title=f'Survival Curve: {domain}' + (f' by {compare_by}' if compare_by else ''),
        xaxis_title='Days Since Entry to At-Risk State',
        yaxis_title='Survival Probability',
        yaxis_tickformat='.0%',
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    
    return fig


# Usage: Compare survival with vs without intervention
fig = plot_survival_curve('Employee Attrition', compare_by='intervention_applied')
fig.show()
```

---

### 5. Hazard Rate Over Time

```python
def plot_hazard_rate(domain: str = 'Employee Attrition'):
    """
    Plot hazard rate (instantaneous risk of event)
    """
    
    query = """
    WITH survival_data AS (
        SELECT 
            survival_time_days,
            event_occurred::INTEGER as event
        FROM fact_survival_events s
        JOIN dim_risk_domain d ON s.domain_key = d.domain_key
        WHERE d.domain_name = %s
    )
    SELECT 
        survival_time_days,
        SUM(event) * 1.0 / COUNT(*) as hazard_rate,
        COUNT(*) as at_risk
    FROM survival_data
    GROUP BY survival_time_days
    ORDER BY survival_time_days
    """
    
    conn = get_connection()
    df = pd.read_sql(query, conn, params=[domain])
    conn.close()
    
    # Smooth hazard rate using rolling window
    df['hazard_smoothed'] = df['hazard_rate'].rolling(window=7, center=True).mean()
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Hazard rate
    fig.add_trace(
        go.Scatter(
            x=df['survival_time_days'],
            y=df['hazard_smoothed'],
            name='Hazard Rate (7-day smoothed)',
            line=dict(color='#E74C3C', width=2)
        ),
        secondary_y=False
    )
    
    # Number at risk
    fig.add_trace(
        go.Scatter(
            x=df['survival_time_days'],
            y=df['at_risk'],
            name='Number at Risk',
            line=dict(color='#95A5A6', width=1, dash='dash')
        ),
        secondary_y=True
    )
    
    fig.update_xaxes(title_text="Days")
    fig.update_yaxes(title_text="Hazard Rate", secondary_y=False)
    fig.update_yaxes(title_text="Number at Risk", secondary_y=True)
    
    fig.update_layout(
        title=f'Hazard Rate Over Time: {domain}',
        hovermode='x unified',
        template='plotly_white',
        height=500
    )
    
    return fig
```

---

## Cohort Analysis Heatmaps

### 6. Cohort Retention Heatmap

```python
def plot_cohort_retention_heatmap(domain: str = 'Employee Attrition'):
    """
    Retention heatmap: rows=cohorts, columns=time periods
    """
    
    query = """
    WITH cohorts AS (
        SELECT 
            TO_CHAR(s.cohort_month, 'YYYY-MM') as cohort,
            s.entity_key,
            s.survival_time_days,
            s.event_occurred
        FROM fact_survival_events s
        JOIN dim_risk_domain d ON s.domain_key = d.domain_key
        WHERE d.domain_name = %s
          AND s.cohort_month >= CURRENT_DATE - INTERVAL '12 months'
    )
    SELECT 
        cohort,
        COUNT(DISTINCT entity_key) as cohort_size,
        COUNT(DISTINCT CASE WHEN survival_time_days >= 30 AND NOT event_occurred THEN entity_key END) as m1,
        COUNT(DISTINCT CASE WHEN survival_time_days >= 60 AND NOT event_occurred THEN entity_key END) as m2,
        COUNT(DISTINCT CASE WHEN survival_time_days >= 90 AND NOT event_occurred THEN entity_key END) as m3,
        COUNT(DISTINCT CASE WHEN survival_time_days >= 120 AND NOT event_occurred THEN entity_key END) as m4,
        COUNT(DISTINCT CASE WHEN survival_time_days >= 150 AND NOT event_occurred THEN entity_key END) as m5,
        COUNT(DISTINCT CASE WHEN survival_time_days >= 180 AND NOT event_occurred THEN entity_key END) as m6
    FROM cohorts
    GROUP BY cohort
    ORDER BY cohort DESC
    """
    
    conn = get_connection()
    df = pd.read_sql(query, conn, params=[domain])
    conn.close()
    
    # Calculate retention rates
    for col in ['m1', 'm2', 'm3', 'm4', 'm5', 'm6']:
        df[f'{col}_pct'] = (df[col] / df['cohort_size'] * 100).round(1)
    
    # Prepare data for heatmap
    heatmap_data = df[[f'm{i}_pct' for i in range(1, 7)]].values
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6'],
        y=df['cohort'],
        colorscale='RdYlGn',
        text=heatmap_data,
        texttemplate='%{text}%',
        textfont={"size": 10},
        colorbar=dict(title="Retention %")
    ))
    
    fig.update_layout(
        title=f'Cohort Retention Analysis: {domain}',
        xaxis_title='Time Period',
        yaxis_title='Cohort Month',
        height=600,
        template='plotly_white'
    )
    
    return fig
```

---

## Interactive Dashboards

### 7. Complete Streamlit Dashboard

```python
# dashboard.py
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Risk Analytics Dashboard", layout="wide")

st.title("🎯 Universal Risk Analytics Dashboard")

# Sidebar filters
st.sidebar.header("Filters")
domain = st.sidebar.selectbox(
    "Risk Domain",
    ["Employee Attrition", "Vulnerability Exploitation", "Customer Churn"]
)

date_range = st.sidebar.date_input(
    "Date Range",
    value=(datetime.now() - timedelta(days=90), datetime.now())
)

# Main dashboard layout
col1, col2, col3, col4 = st.columns(4)

# KPI Cards
with col1:
    st.metric("Total At Risk", "1,234", delta="+12%")

with col2:
    st.metric("Avg Risk Score", "67.5", delta="-2.3")

with col3:
    st.metric("Critical Alerts", "43", delta="+5")

with col4:
    st.metric("Median Survival", "87 days", delta="+12 days")

# Row 1: Risk trends
col1, col2 = st.columns(2)

with col1:
    st.subheader("Risk Distribution Over Time")
    fig1 = plot_risk_distribution_evolution(domain)
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Likelihood vs Impact Matrix")
    fig2 = plot_likelihood_impact_matrix(domain)
    st.plotly_chart(fig2, use_container_width=True)

# Row 2: Survival analysis
st.subheader("Survival Analysis")
tab1, tab2, tab3 = st.tabs(["Survival Curve", "Hazard Rate", "Cohort Analysis"])

with tab1:
    compare_by = st.selectbox("Compare by", [None, "intervention_applied", "risk_trend"])
    fig3 = plot_survival_curve(domain, compare_by=compare_by)
    st.plotly_chart(fig3, use_container_width=True)

with tab2:
    fig4 = plot_hazard_rate(domain)
    st.plotly_chart(fig4, use_container_width=True)

with tab3:
    fig5 = plot_cohort_retention_heatmap(domain)
    st.plotly_chart(fig5, use_container_width=True)

# Row 3: Detailed entity view
st.subheader("Entity Detail View")
entity_id = st.text_input("Enter Entity ID", "USR12345")

if entity_id:
    fig6 = plot_risk_trajectory(entity_id, domain)
    st.plotly_chart(fig6, use_container_width=True)
    
    # Risk drivers
    st.subheader(f"Risk Drivers for {entity_id}")
    # Query and display top risk factors
    # (Add query from analytics guide)

# Footer
st.markdown("---")
st.caption("Data updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
```

**Run dashboard:**
```bash
streamlit run dashboard.py
```

---

## Executive Reports

### 8. PDF Report Generation

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import io

def generate_executive_report(domain: str, output_path: str):
    """
    Generate PDF executive report
    """
    
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"<b>Risk Analytics Report: {domain}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.5*inch))
    
    # Executive Summary
    summary = Paragraph(f"""
        <b>Executive Summary</b><br/><br/>
        As of {datetime.now().strftime('%B %d, %Y')}, the {domain} domain shows...<br/>
        [Auto-generated summary from queries]
    """, styles['BodyText'])
    story.append(summary)
    story.append(Spacer(1, 0.3*inch))
    
    # Add visualizations
    # Convert Plotly figures to images
    fig = plot_risk_distribution_evolution(domain)
    img_bytes = fig.to_image(format="png")
    img = Image(io.BytesIO(img_bytes), width=6*inch, height=3*inch)
    story.append(img)
    
    # Build PDF
    doc.build(story)
    print(f"Report generated: {output_path}")

# Generate report
generate_executive_report("Employee Attrition", "risk_report.pdf")
```

---

## Complete Workflow: Data to Dashboard

```bash
# Step 1: Run ETL to populate data marts
python python/risk_analytics_etl.py

# Step 2: Verify data loaded
psql $DATABASE_URL -c "SELECT COUNT(*) FROM fact_risk_assessment;"

# Step 3: Generate visualizations
python python/visualizations.py

# Step 4: Launch dashboard
streamlit run dashboard.py

# Step 5: Generate executive report
python python/generate_report.py
```

---

This complete toolkit provides everything needed to transform risk assessments into actionable insights through comprehensive visualizations and dashboards!
