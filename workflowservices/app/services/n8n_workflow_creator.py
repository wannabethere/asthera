from typing import Dict, List, Any, Optional
from uuid import UUID
import json
import os
from datetime import datetime
from pathlib import Path

from app.models.workflowmodels import (
    DashboardWorkflow, ThreadComponent, ShareConfiguration,
    ScheduleConfiguration, IntegrationConfig, WorkflowState,
    ComponentType, ShareType, ScheduleType, IntegrationType,
    AlertType, AlertSeverity
)
from app.models.dbmodels import Dashboard


class N8nWorkflowCreator:
    """Service for creating n8n workflows from active dashboards"""
    
    def __init__(self, output_dir: str = "n8n_workflows"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def create_dashboard_workflow(
        self,
        dashboard: Dashboard,
        workflow: DashboardWorkflow,
        components: List[ThreadComponent],
        share_configs: List[ShareConfiguration],
        schedule_config: Optional[ScheduleConfiguration],
        integrations: List[IntegrationConfig]
    ) -> Dict[str, Any]:
        """
        Create an n8n workflow JSON for an active dashboard
        
        Args:
            dashboard: The dashboard object
            workflow: The workflow object
            components: List of thread components
            share_configs: List of sharing configurations
            schedule_config: Optional schedule configuration
            integrations: List of integration configurations
            
        Returns:
            Dict containing the n8n workflow JSON and file path
        """
        
        # Generate workflow structure based on dashboard components and configuration
        n8n_workflow = self._generate_workflow_structure(
            dashboard, workflow, components, share_configs, schedule_config, integrations
        )
        
        # Save to file
        filename = f"dashboard_{dashboard.id}_{workflow.id}.json"
        file_path = self.output_dir / filename
        
        with open(file_path, 'w') as f:
            json.dump(n8n_workflow, f, indent=2, default=str)
        
        return {
            "workflow_json": n8n_workflow,
            "file_path": str(file_path),
            "filename": filename,
            "dashboard_id": str(dashboard.id),
            "workflow_id": str(workflow.id)
        }
    
    def create_report_workflow(
        self,
        report,
        workflow,
        components: List[ThreadComponent],
        share_configs: List[ShareConfiguration],
        schedule_config: Optional[ScheduleConfiguration],
        integrations: List[IntegrationConfig]
    ) -> Dict[str, Any]:
        """
        Create an n8n workflow JSON for an active report following the standardized pattern:
        Trigger/Scheduled Trigger → Start → Call render/alert (API Call) → Check alert condition (API Call) → If yes → Send to integration
        """
        
        # Generate workflow structure based on report components and configuration
        n8n_workflow = self._generate_report_workflow_structure(
            report, workflow, components, share_configs, schedule_config, integrations
        )
        
        # Save to file
        filename = f"report_{report.id}_{workflow.id}.json"
        file_path = self.output_dir / filename
        
        with open(file_path, 'w') as f:
            json.dump(n8n_workflow, f, indent=2, default=str)
        
        return {
            "workflow_json": n8n_workflow,
            "file_path": str(file_path),
            "filename": filename,
            "report_id": str(report.id),
            "workflow_id": str(workflow.id)
        }
    
    def _generate_report_workflow_structure(
        self,
        report,
        workflow,
        components: List[ThreadComponent],
        share_configs: List[ShareConfiguration],
        schedule_config: Optional[ScheduleConfiguration],
        integrations: List[IntegrationConfig]
    ) -> Dict[str, Any]:
        """Generate the standardized n8n workflow structure for reports"""
        
        # Create base workflow
        n8n_workflow = {
            "name": f"Report Workflow - {report.name}",
            "nodes": [],
            "connections": {},
            "active": True,
            "settings": {
                "executionOrder": "v1"
            },
            "versionId": "1.0.0",
            "meta": {
                "instanceId": str(workflow.id),
                "templateCredsSetupCompleted": True
            },
            "tags": [
                {"createdAt": datetime.utcnow().isoformat(), "name": "report"},
                {"createdAt": datetime.utcnow().isoformat(), "name": report.name.lower().replace(" ", "_")}
            ]
        }
        
        # 1. Add trigger node (Manual or Scheduled)
        trigger_node = self._create_trigger_node(schedule_config)
        n8n_workflow["nodes"].append(trigger_node)
        
        # 2. Add Start node
        start_node = self._create_report_start_node()
        n8n_workflow["nodes"].append(start_node)
        
        # 3. Add Render/Alert API Call node
        render_node = self._create_report_render_api_node(report, workflow, components)
        n8n_workflow["nodes"].append(render_node)
        
        # 4. Add Alert Condition Check node (for alert components)
        alert_check_node = self._create_alert_condition_node(components)
        n8n_workflow["nodes"].append(alert_check_node)
        
        # 5. Add Integration nodes (conditionally executed)
        integration_nodes = self._create_integration_nodes(integrations)
        n8n_workflow["nodes"].extend(integration_nodes)
        
        # Create standardized connections
        n8n_workflow["connections"] = self._create_standardized_connections(
            trigger_node, start_node, render_node, alert_check_node, integration_nodes
        )
        
        return n8n_workflow
    
    def _create_report_start_node(self) -> Dict[str, Any]:
        """Create the Start node for report workflows"""
        return {
            "id": "start_node",
            "name": "Start",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.3,
            "position": [460, 300],
            "parameters": {
                "values": {
                    "string": [
                        {
                            "name": "workflow_type",
                            "value": "report"
                        },
                        {
                            "name": "timestamp",
                            "value": "={{ new Date().toISOString() }}"
                        }
                    ]
                }
            }
        }
    
    def _create_report_render_api_node(self, report, workflow, components: List[ThreadComponent]) -> Dict[str, Any]:
        """Create the Render/Alert API Call node for reports"""
        return {
            "id": "render_api_node",
            "name": "Render Report/Alert",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [680, 300],
            "parameters": {
                "url": "{{ $env.BASE_URL }}/api/workflows/{{ $json.workflow_id }}/render-report",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "bodyParameters": {
                    "parameters": [
                        {
                            "name": "report_id",
                            "value": "{{ $json.report_id }}"
                        },
                        {
                            "name": "workflow_id",
                            "value": "{{ $json.workflow_id }}"
                        },
                        {
                            "name": "components",
                            "value": "{{ JSON.stringify($json.components) }}"
                        },
                        {
                            "name": "render_type",
                            "value": "report"
                        }
                    ]
                }
            }
        }
    
    def _generate_workflow_structure(
        self,
        dashboard: Dashboard,
        workflow: DashboardWorkflow,
        components: List[ThreadComponent],
        share_configs: List[ShareConfiguration],
        schedule_config: Optional[ScheduleConfiguration],
        integrations: List[IntegrationConfig]
    ) -> Dict[str, Any]:
        """Generate the standardized n8n workflow structure:
        Trigger/Scheduled Trigger → Start → Call render/alert (API Call) → Check alert condition (API Call) → If yes → Send to integration
        """
        
        # Create base workflow
        n8n_workflow = {
            "name": f"Dashboard Workflow - {dashboard.name}",
            "nodes": [],
            "connections": {},
            "active": True,
            "settings": {
                "executionOrder": "v1"
            },
            "versionId": "1.0.0",
            "meta": {
                "instanceId": str(workflow.id),
                "templateCredsSetupCompleted": True
            },
            "tags": [
                {"createdAt": datetime.utcnow().isoformat(), "name": "dashboard"},
                {"createdAt": datetime.utcnow().isoformat(), "name": dashboard.name.lower().replace(" ", "_")}
            ]
        }
        
        # 1. Add trigger node (Manual or Scheduled)
        trigger_node = self._create_trigger_node(schedule_config)
        n8n_workflow["nodes"].append(trigger_node)
        
        # 2. Add Start node
        start_node = self._create_start_node()
        n8n_workflow["nodes"].append(start_node)
        
        # 3. Add Render/Alert API Call node
        render_node = self._create_render_api_node(dashboard, workflow, components)
        n8n_workflow["nodes"].append(render_node)
        
        # 4. Add Alert Condition Check node (for alert components)
        alert_check_node = self._create_alert_condition_node(components)
        n8n_workflow["nodes"].append(alert_check_node)
        
        # 5. Add Integration nodes (conditionally executed)
        integration_nodes = self._create_integration_nodes(integrations)
        n8n_workflow["nodes"].extend(integration_nodes)
        
        # Create standardized connections
        n8n_workflow["connections"] = self._create_standardized_connections(
            trigger_node, start_node, render_node, alert_check_node, integration_nodes
        )
        
        return n8n_workflow
    
    def _create_start_node(self) -> Dict[str, Any]:
        """Create the Start node that initializes the workflow"""
        return {
            "id": "start_node",
            "name": "Start",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.3,
            "position": [460, 300],
            "parameters": {
                "values": {
                    "string": [
                        {
                            "name": "workflow_type",
                            "value": "dashboard"
                        },
                        {
                            "name": "timestamp",
                            "value": "={{ new Date().toISOString() }}"
                        }
                    ]
                }
            }
        }
    
    def _create_render_api_node(self, dashboard: Dashboard, workflow: DashboardWorkflow, components: List[ThreadComponent]) -> Dict[str, Any]:
        """Create the Render/Alert API Call node"""
        return {
            "id": "render_api_node",
            "name": "Render Dashboard/Alert",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [680, 300],
            "parameters": {
                "url": "{{ $env.BASE_URL }}/api/workflows/{{ $json.workflow_id }}/render",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "bodyParameters": {
                    "parameters": [
                        {
                            "name": "dashboard_id",
                            "value": "{{ $json.dashboard_id }}"
                        },
                        {
                            "name": "workflow_id",
                            "value": "{{ $json.workflow_id }}"
                        },
                        {
                            "name": "components",
                            "value": "{{ JSON.stringify($json.components) }}"
                        },
                        {
                            "name": "render_type",
                            "value": "dashboard"
                        }
                    ]
                }
            }
        }
    
    def _create_alert_condition_node(self, components: List[ThreadComponent]) -> Dict[str, Any]:
        """Create the Alert Condition Check node"""
        # Check if there are any alert components
        has_alerts = any(comp.component_type == ComponentType.ALERT for comp in components)
        
        if not has_alerts:
            # If no alerts, just pass through
            return {
                "id": "alert_check_node",
                "name": "Alert Check (Pass Through)",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.3,
                "position": [900, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "alert_triggered",
                                "value": "false"
                            },
                            {
                                "name": "alert_conditions_met",
                                "value": "false"
                            }
                        ]
                    }
                }
            }
        
        return {
            "id": "alert_check_node",
            "name": "Check Alert Conditions",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [900, 300],
            "parameters": {
                "url": "{{ $env.BASE_URL }}/api/workflows/{{ $json.workflow_id }}/check-alerts",
                "method": "POST",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpBasicAuth",
                "sendBody": True,
                "bodyParameters": {
                    "parameters": [
                        {
                            "name": "dashboard_data",
                            "value": "={{ $json }}"
                        },
                        {
                            "name": "alert_components",
                            "value": "={{ JSON.stringify($json.alert_components) }}"
                        }
                    ]
                }
            }
        }
    
    def _create_trigger_node(self, schedule_config: Optional[ScheduleConfiguration]) -> Dict[str, Any]:
        """Create the trigger node based on schedule configuration"""
        
        if not schedule_config:
            # Default to manual trigger
            return {
                "id": "trigger_manual",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {}
            }
        
        # Create scheduled trigger based on schedule type
        if schedule_config.schedule_type == ScheduleType.CRON:
            return {
                "id": "trigger_cron",
                "name": "Cron Trigger",
                "type": "n8n-nodes-base.cron",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "rule": {
                        "hour": "*",
                        "minute": "0",
                        "dayOfMonth": "*",
                        "month": "*",
                        "dayOfWeek": "*"
                    },
                    "options": {}
                }
            }
        elif schedule_config.schedule_type == ScheduleType.DAILY:
            return {
                "id": "trigger_daily",
                "name": "Daily Trigger",
                "type": "n8n-nodes-base.cron",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "rule": {
                        "hour": "9",
                        "minute": "0",
                        "dayOfMonth": "*",
                        "month": "*",
                        "dayOfWeek": "*"
                    },
                    "options": {}
                }
            }
        elif schedule_config.schedule_type == ScheduleType.WEEKLY:
            return {
                "id": "trigger_weekly",
                "name": "Weekly Trigger",
                "type": "n8n-nodes-base.cron",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "rule": {
                        "hour": "9",
                        "minute": "0",
                        "dayOfMonth": "*",
                        "month": "*",
                        "dayOfWeek": "1"
                    },
                    "options": {}
                }
            }
        else:
            # Default to manual trigger for other types
            return {
                "id": "trigger_manual",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {}
            }
    
    def _create_component_node(self, component: ThreadComponent, index: int) -> Dict[str, Any]:
        """Create a node for a dashboard component"""
        
        base_position = [480 + (index * 200), 300]
        
        if component.component_type == ComponentType.CHART:
            return {
                "id": f"chart_{component.id}",
                "name": f"Chart: {component.question or 'Chart Component'}",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": base_position,
                "parameters": {
                    "jsCode": self._generate_chart_code(component),
                    "options": {}
                }
            }
        elif component.component_type == ComponentType.TABLE:
            return {
                "id": f"table_{component.id}",
                "name": f"Table: {component.question or 'Table Component'}",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": base_position,
                "parameters": {
                    "jsCode": self._generate_table_code(component),
                    "options": {}
                }
            }
        elif component.component_type == ComponentType.METRIC:
            return {
                "id": f"metric_{component.id}",
                "name": f"Metric: {component.question or 'Metric Component'}",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": base_position,
                "parameters": {
                    "jsCode": self._generate_metric_code(component),
                    "options": {}
                }
            }
        elif component.component_type == ComponentType.ALERT:
            return {
                "id": f"alert_{component.id}",
                "name": f"Alert: {component.question or 'Alert Component'}",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": base_position,
                "parameters": {
                    "jsCode": self._generate_alert_code(component),
                    "options": {}
                }
            }
        else:
            # Default to code node for other component types
            return {
                "id": f"component_{component.id}",
                "name": f"{component.component_type.value.title()}: {component.question or 'Component'}",
                "options": {}
            }
    
    def _create_sharing_nodes(self, share_configs: List[ShareConfiguration]) -> List[Dict[str, Any]]:
        """Create nodes for sharing functionality"""
        
        nodes = []
        for i, config in enumerate(share_configs):
            if config.share_type == ShareType.EMAIL:
                nodes.append({
                    "id": f"email_share_{config.id}",
                    "name": f"Email Share: {config.target_id}",
                    "type": "n8n-nodes-base.emailSend",
                    "typeVersion": 2,
                    "position": [1200 + (i * 200), 200],
                    "parameters": {
                        "toEmail": config.target_id,
                        "subject": "Dashboard Update",
                        "text": "Your dashboard has been updated with new data.",
                        "options": {}
                    }
                })
            elif config.share_type == ShareType.SLACK:
                nodes.append({
                    "id": f"slack_share_{config.id}",
                    "name": f"Slack Share: {config.target_id}",
                    "type": "n8n-nodes-base.slack",
                    "typeVersion": 1,
                    "position": [1200 + (i * 200), 200],
                    "parameters": {
                        "channel": config.target_id,
                        "text": "Dashboard update notification",
                        "otherOptions": {}
                    }
                })
            elif config.share_type == ShareType.WEBHOOK:
                nodes.append({
                    "id": f"webhook_share_{config.id}",
                    "name": f"Webhook: {config.target_id}",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.1,
                    "position": [1200 + (i * 200), 200],
                    "parameters": {
                        "url": config.target_id,
                        "method": "POST",
                        "sendBody": True,
                        "bodyParameters": {
                            "parameters": [
                                {
                                    "name": "dashboard_update",
                                    "value": "true"
                                }
                            ]
                        }
                    }
                })
        
        return nodes
    
    def _create_integration_nodes(self, integrations: List[IntegrationConfig]) -> List[Dict[str, Any]]:
        """Create nodes for external integrations"""
        
        nodes = []
        for i, integration in enumerate(integrations):
            if integration.integration_type == IntegrationType.TABLEAU:
                nodes.append({
                    "id": f"tableau_{integration.id}",
                    "name": "Tableau Integration",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.1,
                    "position": [1400 + (i * 200), 400],
                    "parameters": {
                        "url": "https://tableau.example.com/api/dashboards",
                        "method": "POST",
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpBasicAuth",
                        "sendBody": True,
                        "bodyParameters": {
                            "parameters": [
                                {
                                    "name": "dashboard_data",
                                    "value": "={{ $json }}"
                                }
                            ]
                        }
                    }
                })
            elif integration.integration_type == IntegrationType.POWERBI:
                nodes.append({
                    "id": f"powerbi_{integration.id}",
                    "name": "Power BI Integration",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.1,
                    "position": [1400 + (i * 200), 400],
                    "parameters": {
                        "url": "https://api.powerbi.com/v1.0/myorg/datasets",
                        "method": "POST",
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpBasicAuth",
                        "sendBody": True,
                        "bodyParameters": {
                            "parameters": [
                                {
                                    "name": "dashboard_data",
                                    "value": "={{ $json }}"
                                }
                            ]
                        }
                    }
                })
            elif integration.integration_type == IntegrationType.S3:
                nodes.append({
                    "id": f"s3_{integration.id}",
                    "name": "S3 Export",
                    "type": "n8n-nodes-base.awsS3",
                    "typeVersion": 1,
                    "position": [1400 + (i * 200), 400],
                    "parameters": {
                        "operation": "upload",
                        "bucketName": "dashboard-exports",
                        "fileName": "={{ $json.dashboard_name }}_export.json",
                        "binaryData": False,
                        "fileContent": "={{ JSON.stringify($json) }}"
                    }
                })
            elif integration.integration_type == IntegrationType.TEAMS:
                nodes.append({
                    "id": f"teams_{integration.id}",
                    "name": "Microsoft Teams Integration",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [1120 + (i * 200), 400],
                    "parameters": {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict"
                            },
                            "conditions": [
                                {
                                    "id": "condition1",
                                    "leftValue": "={{ $json.alert_triggered }}",
                                    "rightValue": "true",
                                    "operator": {
                                        "type": "string",
                                        "operation": "equals"
                                    }
                                }
                            ],
                            "combinator": "and"
                        },
                        "options": {}
                    }
                })
                
                # Add Teams action node inside the IF condition
                teams_action_node = {
                    "id": f"teams_action_{integration.id}",
                    "name": "Send to Teams",
                    "type": "n8n-nodes-base.microsoftTeams",
                    "typeVersion": 1,
                    "position": [1320 + (i * 200), 300],
                    "parameters": {
                        "operation": "postMessage",
                        "channelId": "={{ $json.mapping_config.channel_id }}",
                        "message": "Dashboard Update: {{ $json.dashboard_name }}",
                        "attachments": [
                            {
                                "contentType": "application/vnd.microsoft.card.adaptive",
                                "content": {
                                    "type": "AdaptiveCard",
                                    "body": [
                                        {
                                            "type": "TextBlock",
                                            "text": "{{ $json.dashboard_name }}",
                                            "weight": "Bolder",
                                            "size": "Medium"
                                        },
                                        {
                                            "type": "TextBlock",
                                            "text": "{{ $json.dashboard_description }}",
                                            "wrap": True
                                        }
                                    ],
                                    "actions": [
                                        {
                                            "type": "Action.OpenUrl",
                                            "title": "View Dashboard",
                                            "url": "={{ $json.dashboard_url }}"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
                nodes.append(teams_action_node)
            elif integration.integration_type == IntegrationType.CORNERSTONE:
                nodes.append({
                    "id": f"cornerstone_{integration.id}",
                    "name": "Cornerstone Integration Check",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2,
                    "position": [1120 + (i * 200), 500],
                    "parameters": {
                        "conditions": {
                            "options": {
                                "caseSensitive": True,
                                "leftValue": "",
                                "typeValidation": "strict"
                            },
                            "conditions": [
                                {
                                    "id": "condition1",
                                    "leftValue": "={{ $json.alert_triggered }}",
                                    "rightValue": "true",
                                    "operator": {
                                        "type": "string",
                                        "operation": "equals"
                                    }
                                }
                            ],
                            "combinator": "and"
                        },
                        "options": {}
                    }
                })
                
                # Add Cornerstone action node inside the IF condition
                cornerstone_action_node = {
                    "id": f"cornerstone_action_{integration.id}",
                    "name": "Publish to Cornerstone",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.1,
                    "position": [1320 + (i * 200), 500],
                    "parameters": {
                        "url": "https://api.cornerstoneondemand.com/api/v1/courses/{{ $json.mapping_config.course_id }}/modules/{{ $json.mapping_config.module_id }}/content",
                        "method": "POST",
                        "authentication": "genericCredentialType",
                        "genericAuthType": "httpBasicAuth",
                        "sendBody": True,
                        "bodyParameters": {
                            "parameters": [
                                {
                                    "name": "content_type",
                                    "value": "dashboard"
                                },
                                {
                                    "name": "title",
                                    "value": "={{ $json.dashboard_name }}"
                                },
                                {
                                    "name": "description",
                                    "value": "={{ $json.dashboard_description }}"
                                },
                                {
                                    "name": "dashboard_data",
                                    "value": "={{ JSON.stringify($json) }}"
                                },
                                {
                                    "name": "dashboard_url",
                                    "value": "={{ $json.dashboard_url }}"
                                }
                            ]
                        }
                    }
                }
                nodes.append(cornerstone_action_node)
        
        return nodes
    
    def _create_standardized_connections(
        self,
        trigger_node: Dict[str, Any],
        start_node: Dict[str, Any],
        render_node: Dict[str, Any],
        alert_check_node: Dict[str, Any],
        integration_nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create standardized connections following the pattern:
        Trigger → Start → Render/Alert → Check Alert Condition → (If yes) → Send to Integration
        """
        
        connections = {}
        
        # 1. Trigger → Start
        connections[trigger_node["id"]] = {
            "main": [
                [
                    {
                        "node": start_node["id"],
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        }
        
        # 2. Start → Render/Alert
        connections[start_node["id"]] = {
            "main": [
                [
                    {
                        "node": render_node["id"],
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        }
        
        # 3. Render/Alert → Alert Check
        connections[render_node["id"]] = {
            "main": [
                [
                    {
                        "node": alert_check_node["id"],
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        }
        
        # 4. Alert Check → Integrations (conditional)
        if integration_nodes:
            # Connect to all integration check nodes in parallel
            integration_connections = []
            for integration_node in integration_nodes:
                # Only connect to the IF condition nodes, not the action nodes
                if integration_node["type"] == "n8n-nodes-base.if":
                    integration_connections.append({
                        "node": integration_node["id"],
                        "type": "main",
                        "index": 0
                    })
            
            connections[alert_check_node["id"]] = {
                "main": [
                    integration_connections
                ]
            }
            
            # Add connections from IF condition nodes to their action nodes
            for i, integration_node in enumerate(integration_nodes):
                if integration_node["type"] == "n8n-nodes-base.if":
                    # Find the corresponding action node
                    action_node_id = f"{integration_node['id'].replace('_', '_action_')}"
                    connections[integration_node["id"]] = {
                        "main": [
                            [
                                {
                                    "node": action_node_id,
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
        
        return connections
    
    def _create_node_connections(
        self,
        trigger_node: Dict[str, Any],
        component_nodes: List[Dict[str, Any]],
        sharing_nodes: List[Dict[str, Any]],
        integration_nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create connections between all nodes"""
        
        connections = {}
        
        # Connect trigger to first component
        if component_nodes:
            connections[trigger_node["id"]] = {
                "main": [
                    [
                        {
                            "node": component_nodes[0]["id"],
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        
        # Connect components in sequence
        for i in range(len(component_nodes) - 1):
            current_node = component_nodes[i]
            next_node = component_nodes[i + 1]
            
            connections[current_node["id"]] = {
                "main": [
                    [
                        {
                            "node": next_node["id"],
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        
        # Connect last component to sharing nodes
        if component_nodes and sharing_nodes:
            last_component = component_nodes[-1]
            connections[last_component["id"]] = {
                "main": [
                    [
                        {
                            "node": sharing_nodes[0]["id"],
                            "type": "main",
                            "index": 0
                        }
                    ]
                ]
            }
        
        # Connect sharing nodes to integration nodes
        if sharing_nodes and integration_nodes:
            for i, sharing_node in enumerate(sharing_nodes):
                if i < len(integration_nodes):
                    connections[sharing_node["id"]] = {
                        "main": [
                            [
                                {
                                    "node": integration_nodes[i]["id"],
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
        
        return connections
    
    def _generate_chart_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for chart components"""
        
        chart_config = component.chart_config or {}
        chart_type = chart_config.get("type", "bar")
        
        return f"""
// Chart Component: {component.question or 'Chart'}
const chartData = {{
    type: '{chart_type}',
    data: $input.all()[0].json,
    config: {json.dumps(chart_config)}
}};

// Process chart data
const processedData = {{
    chart_type: chartData.type,
    data: chartData.data,
    configuration: chartData.config,
    component_id: '{component.id}',
    timestamp: new Date().toISOString()
}};

return [processedData];
"""
    
    def _generate_table_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for table components"""
        
        table_config = component.table_config or {}
        
        return f"""
// Table Component: {component.question or 'Table'}
const tableData = {{
    columns: {json.dumps(table_config.get('columns', []))},
    data: $input.all()[0].json,
    config: {json.dumps(table_config)}
}};

// Process table data
const processedData = {{
    component_type: 'table',
    columns: tableData.columns,
    data: tableData.data,
    configuration: tableData.config,
    component_id: '{component.id}',
    timestamp: new Date().toISOString()
}};

return [processedData];
"""
    
    def _generate_metric_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for metric components"""
        
        return f"""
// Metric Component: {component.question or 'Metric'}
const inputData = $input.all()[0].json;

// Calculate metric value
const metricValue = {{
    value: inputData.value || 0,
    unit: inputData.unit || '',
    trend: inputData.trend || 'neutral',
    component_id: '{component.id}',
    timestamp: new Date().toISOString()
}};

return [metricValue];
"""
    
    def _generate_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for alert components"""
        
        alert_config = component.alert_config or {}
        alert_type = alert_config.get("alert_type", "threshold")
        severity = alert_config.get("severity", "medium")
        condition_config = alert_config.get("condition_config", {})
        
        if alert_type == "threshold":
            return self._generate_threshold_alert_code(component)
        elif alert_type == "anomaly":
            return self._generate_anomaly_alert_code(component)
        elif alert_type == "trend":
            return self._generate_trend_alert_code(component)
        elif alert_type == "comparison":
            return self._generate_comparison_alert_code(component)
        elif alert_type == "schedule":
            return self._generate_schedule_alert_code(component)
        else:
            return self._generate_generic_alert_code(component)
    
    def _generate_threshold_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for threshold alerts"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        field = condition_config.get("field", "value")
        operator = condition_config.get("operator", ">")
        threshold_value = condition_config.get("threshold_value", 0)
        
        return f"""
// Threshold Alert: {component.question or 'Threshold Alert'}
const inputData = $input.all()[0].json;
const field = '{field}';
const operator = '{operator}';
const threshold = {threshold_value};
const severity = '{alert_config.get("severity", "medium")}';

// Get the value to check
const actualValue = inputData[field];
let triggered = false;

// Evaluate threshold condition
if (operator === '>') {{
    triggered = actualValue > threshold;
}} else if (operator === '>=') {{
    triggered = actualValue >= threshold;
}} else if (operator === '<') {{
    triggered = actualValue < threshold;
}} else if (operator === '<=') {{
    triggered = actualValue <= threshold;
}} else if (operator === '==') {{
    triggered = actualValue === threshold;
}} else if (operator === '!=') {{
    triggered = actualValue !== threshold;
}}

// Create alert result
const alertResult = {{
    alert_id: '{component.id}',
    alert_name: '{component.question or "Threshold Alert"}',
    alert_type: 'threshold',
    severity: severity,
    triggered: triggered,
    field: field,
    operator: operator,
    threshold: threshold,
    actual_value: actualValue,
    timestamp: new Date().toISOString(),
    notification_channels: {json.dumps(alert_config.get("notification_channels", []))}
}};

return [alertResult];
"""
    
    def _generate_anomaly_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for anomaly detection alerts"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        anomaly_config = alert_config.get("anomaly_config", {})
        field = condition_config.get("field", "value")
        method = anomaly_config.get("method", "zscore")
        sensitivity = anomaly_config.get("sensitivity", 2.0)
        
        return f"""
// Anomaly Alert: {component.question or 'Anomaly Alert'}
const inputData = $input.all()[0].json;
const field = '{field}';
const method = '{method}';
const sensitivity = {sensitivity};
const severity = '{alert_config.get("severity", "medium")}';

// Get the value to check
const actualValue = inputData[field];

// Placeholder anomaly detection logic
// In production, this would use historical data and statistical methods
let triggered = false;
let anomalyScore = 0;

// Simple example: check if value is outside expected range
// This is a placeholder - real implementation would be more sophisticated
if (method === 'zscore') {{
    // Placeholder z-score calculation
    anomalyScore = Math.random(); // Replace with actual calculation
    triggered = anomalyScore > sensitivity;
}} else if (method === 'iqr') {{
    // Placeholder IQR method
    anomalyScore = Math.random(); // Replace with actual calculation
    triggered = anomalyScore > sensitivity;
}}

// Create alert result
const alertResult = {{
    alert_id: '{component.id}',
    alert_name: '{component.question or "Anomaly Alert"}',
    alert_type: 'anomaly',
    severity: severity,
    triggered: triggered,
    field: field,
    method: method,
    sensitivity: sensitivity,
    anomaly_score: anomalyScore,
    actual_value: actualValue,
    timestamp: new Date().toISOString(),
    notification_channels: {json.dumps(alert_config.get("notification_channels", []))}
}};

return [alertResult];
"""
    
    def _generate_trend_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for trend analysis alerts"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        trend_config = alert_config.get("trend_config", {})
        field = condition_config.get("field", "value")
        trend_direction = condition_config.get("trend_direction", "increasing")
        period = condition_config.get("period", "daily")
        
        return f"""
// Trend Alert: {component.question or 'Trend Alert'}
const inputData = $input.all()[0].json;
const field = '{field}';
const trendDirection = '{trend_direction}';
const period = '{period}';
const severity = '{alert_config.get("severity", "medium")}';

// Get the value to check
const actualValue = inputData[field];

// Placeholder trend analysis logic
// In production, this would analyze historical data patterns
let triggered = false;
let trendStrength = 0;

// Simple example: check trend direction
// This is a placeholder - real implementation would analyze time series data
if (trendDirection === 'increasing') {{
    // Placeholder increasing trend check
    trendStrength = Math.random(); // Replace with actual trend calculation
    triggered = trendStrength > 0.7; // Threshold for trend strength
}} else if (trendDirection === 'decreasing') {{
    // Placeholder decreasing trend check
    trendStrength = Math.random(); // Replace with actual trend calculation
    triggered = trendStrength < -0.7; // Threshold for trend strength
}}

// Create alert result
const alertResult = {{
    alert_id: '{component.id}',
    alert_name: '{component.question or "Trend Alert"}',
    alert_type: 'trend',
    severity: severity,
    triggered: triggered,
    field: field,
    trend_direction: trendDirection,
    period: period,
    trend_strength: trendStrength,
    actual_value: actualValue,
    timestamp: new Date().toISOString(),
    notification_channels: {json.dumps(alert_config.get("notification_channels", []))}
}};

return [alertResult];
"""
    
    def _generate_comparison_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for comparison-based alerts"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        field1 = condition_config.get("field1", "value1")
        field2 = condition_config.get("field2", "value2")
        operator = condition_config.get("operator", ">")
        
        return f"""
// Comparison Alert: {component.question or 'Comparison Alert'}
const inputData = $input.all()[0].json;
const field1 = '{field1}';
const field2 = '{field2}';
const operator = '{operator}';
const severity = '{alert_config.get("severity", "medium")}';

// Get values from data
const value1 = inputData[field1];
const value2 = inputData[field2];

// Evaluate comparison
let triggered = false;
if (operator === '>') {{
    triggered = value1 > value2;
}} else if (operator === '>=') {{
    triggered = value1 >= value2;
}} else if (operator === '<') {{
    triggered = value1 < value2;
}} else if (operator === '<=') {{
    triggered = value1 <= value2;
}} else if (operator === '==') {{
    triggered = value1 === value2;
}} else if (operator === '!=') {{
    triggered = value1 !== value2;
}}

// Create alert result
const alertResult = {{
    alert_id: '{component.id}',
    alert_name: '{component.question or "Comparison Alert"}',
    alert_type: 'comparison',
    severity: severity,
    triggered: triggered,
    field1: field1,
    field2: field2,
    operator: operator,
    value1: value1,
    value2: value2,
    timestamp: new Date().toISOString(),
    notification_channels: {json.dumps(alert_config.get("notification_channels", []))}
}};

return [alertResult];
"""
    
    def _generate_schedule_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for schedule-based alerts"""
        
        alert_config = component.alert_config or {}
        condition_config = alert_config.get("condition_config", {})
        schedule_type = condition_config.get("schedule_type", "daily")
        time = condition_config.get("time", "09:00")
        days = condition_config.get("days", ["monday", "tuesday", "wednesday", "thursday", "friday"])
        
        return f"""
// Schedule Alert: {component.question or 'Schedule Alert'}
const inputData = $input.all()[0].json;
const scheduleType = '{schedule_type}';
const time = '{time}';
const days = {json.dumps(days)};
const severity = '{alert_config.get("severity", "medium")}';

// Placeholder: would check if current time matches schedule
let triggered = false;

// Create alert result
const alertResult = {{
    alert_id: '{component.id}',
    alert_name: '{component.question or "Schedule Alert"}',
    alert_type: 'schedule',
    severity: severity,
    triggered: triggered,
    schedule_type: scheduleType,
    time: time,
    days: days,
    timestamp: new Date().toISOString(),
    notification_channels: {json.dumps(alert_config.get("notification_channels", []))}
}};

return [alertResult];
"""
    
    def _generate_generic_alert_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for generic alerts"""
        
        alert_config = component.alert_config or {}
        
        return f"""
// Generic Alert: {component.question or 'Generic Alert'}
const inputData = $input.all()[0].json;
const severity = '{alert_config.get("severity", "medium")}';

// Generic alert evaluation
// This can be customized based on specific alert requirements
let triggered = false;

// Placeholder logic - customize based on alert type
// triggered = evaluateCustomCondition(inputData);

// Create alert result
const alertResult = {{
    alert_id: '{component.id}',
    alert_name: '{component.question or "Generic Alert"}',
    alert_type: '{alert_config.get("alert_type", "generic")}',
    severity: severity,
    triggered: triggered,
    data: inputData,
    timestamp: new Date().toISOString(),
    notification_channels: {json.dumps(alert_config.get("notification_channels", []))}
}};

return [alertResult];
"""
    
    def _generate_generic_code(self, component: ThreadComponent) -> str:
        """Generate JavaScript code for generic components"""
        
        return f"""
// Generic Component: {component.component_type.value}
const inputData = $input.all()[0].json;

// Process component data
const processedData = {{
    component_type: '{component.component_type.value}',
    question: '{component.question or ''}',
    description: '{component.description or ''}',
    data: inputData,
    configuration: {json.dumps(component.configuration)},
    component_id: '{component.id}',
    timestamp: new Date().toISOString()
}};

return [processedData];
"""
    
    def get_workflow_file_path(self, dashboard_id: UUID, workflow_id: UUID) -> Optional[str]:
        """Get the file path for a specific workflow if it exists"""
        
        filename = f"dashboard_{dashboard_id}_{workflow_id}.json"
        file_path = self.output_dir / filename
        
        if file_path.exists():
            return str(file_path)
        return None
    
    def list_workflow_files(self) -> List[Dict[str, Any]]:
        """List all generated workflow files"""
        
        workflow_files = []
        for file_path in self.output_dir.glob("dashboard_*.json"):
            try:
                with open(file_path, 'r') as f:
                    workflow_data = json.load(f)
                
                workflow_files.append({
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "workflow_name": workflow_data.get("name", "Unknown"),
                    "created_at": file_path.stat().st_mtime,
                    "size": file_path.stat().st_size
                })
            except Exception as e:
                # Skip files that can't be read
                continue
        
        return workflow_files
    
    def delete_workflow_file(self, dashboard_id: UUID, workflow_id: UUID) -> bool:
        """Delete a specific workflow file"""
        
        filename = f"dashboard_{dashboard_id}_{workflow_id}.json"
        file_path = self.output_dir / filename
        
        if file_path.exists():
            file_path.unlink()
            return True
        return False
