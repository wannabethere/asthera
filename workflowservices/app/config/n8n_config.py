"""
Configuration settings for the n8n workflow creator
"""

import os
from pathlib import Path
from typing import Dict, Any

# Default output directory for generated n8n workflows
DEFAULT_OUTPUT_DIR = os.getenv("N8N_WORKFLOW_OUTPUT_DIR", "n8n_workflows")

# Supported n8n node types
SUPPORTED_NODE_TYPES = {
    "trigger": [
        "n8n-nodes-base.manualTrigger",
        "n8n-nodes-base.cron",
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.scheduleTrigger"
    ],
    "data_processing": [
        "n8n-nodes-base.code",
        "n8n-nodes-base.function",
        "n8n-nodes-base.set",
        "n8n-nodes-base.merge"
    ],
    "sharing": [
        "n8n-nodes-base.emailSend",
        "n8n-nodes-base.slack",
        "n8n-nodes-base.microsoftTeams",
        "n8n-nodes-base.discord"
    ],
    "integrations": [
        "n8n-nodes-base.httpRequest",
        "n8n-nodes-base.awsS3",
        "n8n-nodes-base.googleSheets",
        "n8n-nodes-base.postgres",
        "n8n-nodes-base.mysql"
    ]
}

# Default node positions for workflow layout
NODE_POSITIONS = {
    "trigger": [240, 300],
    "component": [480, 300],
    "sharing": [1200, 200],
    "integration": [1400, 400]
}

# Spacing between nodes
NODE_SPACING = {
    "horizontal": 200,
    "vertical": 100
}

# Default workflow settings
DEFAULT_WORKFLOW_SETTINGS = {
    "executionOrder": "v1",
    "versionId": "1.0.0",
    "active": True
}

# Workflow metadata configuration
WORKFLOW_META = {
    "templateCredsSetupCompleted": True,
    "instanceId": None,  # Will be set dynamically
    "tags": ["dashboard", "automated"]
}

# Component code templates
COMPONENT_CODE_TEMPLATES = {
    "chart": """
// Chart Component: {component_name}
const chartData = {{
    type: '{chart_type}',
    data: $input.all()[0].json,
    config: {chart_config}
}};

// Process chart data
const processedData = {{
    chart_type: chartData.type,
    data: chartData.data,
    configuration: chartData.config,
    component_id: '{component_id}',
    timestamp: new Date().toISOString()
}};

return [processedData];
""",
    
    "table": """
// Table Component: {component_name}
const tableData = {{
    columns: {columns},
    data: $input.all()[0].json,
    config: {table_config}
}};

// Process table data
const processedData = {{
    component_type: 'table',
    columns: tableData.columns,
    data: tableData.data,
    configuration: tableData.config,
    component_id: '{component_id}',
    timestamp: new Date().toISOString()
}};

return [processedData];
""",
    
    "metric": """
// Metric Component: {component_name}
const inputData = $input.all()[0].json;

// Calculate metric value
const metricValue = {{
    value: inputData.value || 0,
    unit: inputData.unit || '',
    trend: inputData.trend || 'neutral',
    component_id: '{component_id}',
    timestamp: new Date().toISOString()
}};

return [metricValue];
""",
    
    "generic": """
// Generic Component: {component_type}
const inputData = $input.all()[0].json;

// Process component data
const processedData = {{
    component_type: '{component_type}',
    question: '{question}',
    description: '{description}',
    data: inputData,
    configuration: {configuration},
    component_id: '{component_id}',
    timestamp: new Date().toISOString()
}};

return [processedData];
"""
}

# Integration configuration templates
INTEGRATION_CONFIGS = {
    "tableau": {
        "url": "https://tableau.example.com/api/dashboards",
        "method": "POST",
        "auth_type": "httpBasicAuth",
        "body_params": [
            {"name": "dashboard_data", "value": "={{ $json }}"}
        ]
    },
    "powerbi": {
        "url": "https://api.powerbi.com/v1.0/myorg/datasets",
        "method": "POST",
        "auth_type": "httpBasicAuth",
        "body_params": [
            {"name": "dashboard_data", "value": "={{ $json }}"}
        ]
    },
    "slack": {
        "node_type": "n8n-nodes-base.slack",
        "type_version": 1,
        "params": {
            "text": "Dashboard update notification",
            "otherOptions": {}
        }
    },
    "s3": {
        "node_type": "n8n-nodes-base.awsS3",
        "type_version": 1,
        "params": {
            "operation": "upload",
            "bucketName": "dashboard-exports",
            "fileName": "={{ $json.dashboard_name }}_export.json",
            "binaryData": False,
            "fileContent": "={{ JSON.stringify($json) }}"
        }
    }
}

# Schedule configuration templates
SCHEDULE_CONFIGS = {
    "daily": {
        "hour": "9",
        "minute": "0",
        "dayOfMonth": "*",
        "month": "*",
        "dayOfWeek": "*"
    },
    "weekly": {
        "hour": "9",
        "minute": "0",
        "dayOfMonth": "*",
        "month": "*",
        "dayOfWeek": "1"
    },
    "monthly": {
        "hour": "9",
        "minute": "0",
        "dayOfMonth": "1",
        "month": "*",
        "dayOfWeek": "*"
    },
    "hourly": {
        "hour": "*",
        "minute": "0",
        "dayOfMonth": "*",
        "month": "*",
        "dayOfWeek": "*"
    }
}

# Error handling configuration
ERROR_HANDLING = {
    "max_retries": 3,
    "retry_delay": 5,  # seconds
    "log_errors": True,
    "continue_on_error": True
}

# File management configuration
FILE_MANAGEMENT = {
    "max_file_size": 10 * 1024 * 1024,  # 10MB
    "file_retention_days": 90,
    "backup_enabled": True,
    "backup_directory": "n8n_workflows_backup"
}

# Security configuration
SECURITY = {
    "encrypt_sensitive_data": True,
    "encryption_algorithm": "AES-256",
    "key_rotation_days": 30,
    "audit_logging": True
}

def get_n8n_config() -> Dict[str, Any]:
    """Get the complete n8n configuration"""
    
    return {
        "output_dir": DEFAULT_OUTPUT_DIR,
        "supported_nodes": SUPPORTED_NODE_TYPES,
        "node_positions": NODE_POSITIONS,
        "node_spacing": NODE_SPACING,
        "workflow_settings": DEFAULT_WORKFLOW_SETTINGS,
        "workflow_meta": WORKFLOW_META,
        "code_templates": COMPONENT_CODE_TEMPLATES,
        "integration_configs": INTEGRATION_CONFIGS,
        "schedule_configs": SCHEDULE_CONFIGS,
        "error_handling": ERROR_HANDLING,
        "file_management": FILE_MANAGEMENT,
        "security": SECURITY
    }

def get_output_directory() -> Path:
    """Get the configured output directory"""
    
    output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    return output_dir

def get_node_type_info(node_category: str) -> list:
    """Get supported node types for a category"""
    
    return SUPPORTED_NODE_TYPES.get(node_category, [])

def get_component_template(template_type: str) -> str:
    """Get code template for a component type"""
    
    return COMPONENT_CODE_TEMPLATES.get(template_type, COMPONENT_CODE_TEMPLATES["generic"])

def get_integration_config(integration_type: str) -> Dict[str, Any]:
    """Get configuration for an integration type"""
    
    return INTEGRATION_CONFIGS.get(integration_type, {})

def get_schedule_config(schedule_type: str) -> Dict[str, str]:
    """Get configuration for a schedule type"""
    
    return SCHEDULE_CONFIGS.get(schedule_type, {})
