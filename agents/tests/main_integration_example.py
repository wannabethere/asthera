"""
Example integration showing how to modify main.py to use alert_service.py with compatibility

This example shows how to integrate the compatibility wrapper with your existing main.py
while keeping minimal changes to your application.
"""

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
import traceback
import uuid

# Import the compatibility models and wrapper from the merged alert_service
from .alert_service import (
    Condition, AlertResponseCompatibility, Configs, AlertCreate,
    AlertServiceCompatibility, create_alert_service_with_compatibility
)

load_dotenv()

# Global session storage (in production, use Redis or database)
sessions = {}

class AIAlertsService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1, top_p=1.0)
        self.chatHistory = []
        self.stored_configs = None  # Store configs for multi-turn conversations
        
        # Initialize the alert service and compatibility wrapper
        self.alert_service, self.compatibility_wrapper = create_alert_service_with_compatibility()

    async def createAlerts(self, input_text: str, configs: Optional[Configs] = None):
        # Handle multi-turn conversations: use stored configs if new ones aren't provided
        if configs is not None:
            # Normalize and validate configs before storing
            configs = self._normalize_configs(configs)
            # Store configs for potential multi-turn conversation
            self.stored_configs = configs
            current_configs = configs
        elif self.stored_configs is not None:
            # Use previously stored configs for follow-up questions
            current_configs = self.stored_configs
        else:
            raise ValueError("No configuration provided and no stored configuration available")
        
        # Convert configs to the expected supportedJson format
        supportedJson = {
            "Question": current_configs.question,
            "metricsavailable": current_configs.availableMetrics,
            "conditions": current_configs.conditionTypes,
            "schedule": current_configs.schedule,
            "timecolumn": current_configs.timecolumn,
            "notificationgroups": current_configs.notificationgroups
        }
        
        systemPrompt, userPrompt = self.promptGenerator(input_text, supportedJson)

        # Ensure system prompt is added only once at the beginning
        if not any(isinstance(msg, SystemMessage) for msg in self.chatHistory):
            self.chatHistory.insert(0, SystemMessage(content=systemPrompt))

        # Maintain only last 10 Human+AI conversation pairs (20 messages total), but keep system prompt
        non_system_messages = [msg for msg in self.chatHistory if not isinstance(msg, SystemMessage)]
        if len(non_system_messages) >= 20:  # 10 conversations = 20 messages
            # Keep system prompt and last 18 messages (9 conversations) to make room for new pair
            system_messages = [msg for msg in self.chatHistory if isinstance(msg, SystemMessage)]
            self.chatHistory = system_messages + non_system_messages[-18:]

        # Add new human message
        self.chatHistory.append(HumanMessage(content=userPrompt))
        
        try:
            response = await self.llm.ainvoke(self.chatHistory)
            ai_response = response.content
            
            # Add AI response to history
            self.chatHistory.append(AIMessage(content=ai_response))
            
            # Try to parse as JSON to validate structure
            try:
                json_response = json.loads(ai_response)
                # Validate against our AlertResponse model if it's a finished type
                if json_response.get("type") == "finished":
                    # Parse as AlertResponseCompatibility for validation
                    alert_response = AlertResponseCompatibility(**json_response)
                    
                    # NEW: Convert to alert service format and create the alert
                    try:
                        service_response = await self.compatibility_wrapper.create_alerts_from_response(
                            alert_response=alert_response,
                            project_id="default_project",  # You might want to pass this as a parameter
                            session_id=getattr(self, 'current_session_id', None)
                        )
                        
                        # Add service response info to the JSON response
                        json_response["service_created"] = service_response.success
                        json_response["service_metadata"] = service_response.metadata
                        
                        # Update the AI response with the enhanced information
                        ai_response = json.dumps(json_response, indent=2)
                        
                    except Exception as service_error:
                        print(f"Warning: Could not create alert in service: {service_error}")
                        # Continue with the original response even if service creation fails
                        
            except json.JSONDecodeError:
                # It's probably a clarification question, which is fine
                pass
            except Exception as e:
                print(f"Response validation warning: {e}")
                # Continue anyway as it might still be a valid response
            
            return ai_response
            
        except Exception as e:
            print(f"Error getting AI response: {e}")
            raise
    
    def _normalize_configs(self, configs: Configs) -> Configs:
        """Normalize common typos and variations in config values"""
        
        # Normalize condition types
        condition_mapping = {
            "greater than": "greaterthan",
            "greater_than": "greaterthan", 
            "gt": "greaterthan",
            "less than": "lessthan",
            "less_than": "lessthan",
            "lt": "lessthan",
            "equals": "equals",
            "equal": "equals",
            "contains": "contains",
            "not like": "notlike",
            "not_like": "notlike",
            "anomaly detection": "anomalydetection",
            "anomaly_detection": "anomalydetection"
        }
        
        normalized_conditions = []
        for condition in configs.conditionTypes:
            normalized = condition_mapping.get(condition.lower().strip(), condition.lower().strip())
            normalized_conditions.append(normalized)
        
        # Normalize schedule
        schedule_mapping = {
            "daily": "daily",
            "day": "daily", 
            "weekly": "weekly",
            "week": "weekly",
            "monthly": "monthly",
            "month": "monthly",
            "immediately": "immediately",
            "immediate": "immediately",
            "instant": "immediately"
        }
        
        normalized_schedule = []
        for sched in configs.schedule:
            normalized = schedule_mapping.get(sched.lower().strip(), sched.lower().strip())
            normalized_schedule.append(normalized)
        
        # Create new configs object with normalized values
        return Configs(
            conditionTypes=normalized_conditions,
            notificationgroups=[group.strip() for group in configs.notificationgroups],
            schedule=normalized_schedule,
            timecolumn=[tc.lower().strip() for tc in configs.timecolumn],
            availableMetrics=[metric.strip() for metric in configs.availableMetrics],
            question=configs.question.strip()
        )

    def promptGenerator(self, input_text: str, supportedJson: dict):
        # ... (same as original promptGenerator method)
        systemprompt = """
You are an expert AI assistant specializing in creating monitoring alerts from natural language. Your primary function is to interpret a user's request to create an alert, analyze a provided `supportedJson` for available metrics and conditions, and generate a structured JSON output for the alert configuration. You must operate based on the entire conversation history provided.

**Your Task:**
Analyze the user's request and the `supportedJson` to generate a valid JSON alert configuration.

**Strict Rules:**
1.  **JSON Output Only:** If you have enough information, your entire response must be ONLY the JSON object. Do not include any conversational text, explanations, or markdown formatting.
2.  **Ask for Clarification:** If any piece of information required for a condition (metric, operator, value, or frequency) is missing, you MUST ask a clarifying question. Do not guess.
3.  **Strict Mapping:** The values for `metricselected`, `conditionType`, and `rolling` in your output JSON MUST map directly to the options provided in the `supportedJson`.
4.  **Alert Name Generation:** Create a concise and descriptive `alertname` based on the user's intent.
5.  **Question Field:** The `question` field in the output JSON must be copied exactly from the `Question` field in the `supportedJson`.

**Required JSON Structure for Finished Alerts:**
```json
{
  "type": "finished",
  "question": "exact copy from supportedJson Question field",
  "alertname": "descriptive alert name",
  "summary": "brief description of what the alert monitors",
  "reasoning": "explanation of why these conditions were chosen",
  "conditions": [
    {
      "conditionType": "must match supportedJson conditions",
      "metricselected": "must match supportedJson metricsavailable",
      "schedule": "must match supportedJson schedule",
      "timecolumn": "must match supportedJson timecolumn",
      "value": "threshold value or null for anomaly detection"
    }
  ],
  "notificationgroup": "must match one from supportedJson notificationgroups"
}
```

**Few-Shot Examples:**
---
**Example 1: Single Condition with Specific Notification Channel**

* User Input: "Hey, I want to create an alert. If the dropout rate is greater than 10%, send a weekly notification to the retention-team Slack channel."
* supportedJson: {"Question": "What is the overall dropout rate?", "metricsavailable": ["dropout_rate", "completion_rate"], "conditions": ["greaterthan", "lessthan"], "schedule": ["daily", "weekly", "monthly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["slack retention-team", "teams analytics", "email"]}
* Your Output: {"type": "finished", "question": "What is the overall dropout rate?", "alertname": "High Dropout Rate Alert", "summary": "This alert monitors dropout rate weekly and notifies retention team when it exceeds 10%.", "reasoning": "User requested weekly monitoring of dropout rate with greaterthan 10% condition for slack notification.", "conditions": [{"conditionType": "greaterthan", "metricselected": "dropout_rate", "schedule": "weekly", "timecolumn": "rolling", "value": "10"}], "notificationgroup": "slack retention-team"}

**Example 2: Clarification Needed - Missing Threshold**

* User Input: "I'm worried our new hires aren't engaged with their onboarding content."
* supportedJson: {"Question": "What is the engagement level of new hires?", "metricsavailable": ["avg_time_spent_hrs", "onboarding_completion_rate"], "conditions": ["lessthan", "greaterthan"], "schedule": ["daily", "weekly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack onboarding-team", "teams hr-analytics"]}
* Your Output: I can help set up an alert for that. To measure engagement, should I use 'avg_time_spent_hrs' or 'onboarding_completion_rate'? Also, what threshold should I consider as low engagement, and how often should I check (daily or weekly)?

**Example 3: Multiple Conditions on Same Metric with Different Schedules**

* User Input: "For the Q3 sales certification, email me daily if the average score is above 95%, but I need an immediate Slack alert if it ever drops below 60%."
* supportedJson: {"Question": "What are the assessment scores for the Q3 sales certification?", "metricsavailable": ["average_score"], "conditions": ["greaterthan", "lessthan"], "schedule": ["daily", "immediately"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack sales-team", "teams training-analytics"]}
* Your Output: {"type": "finished", "question": "What are the assessment scores for the Q3 sales certification?", "alertname": "Sales Certification Score Thresholds", "summary": "This alert monitors Q3 sales certification scores with dual notifications - daily email for high performance (>95%) and immediate slack alert for critical low scores (<60%).", "reasoning": "User specified two different conditions on same metric with different schedules and notification channels.", "conditions": [{"conditionType": "greaterthan", "metricselected": "average_score", "schedule": "daily", "timecolumn": "rolling", "value": "95"}, {"conditionType": "lessthan", "metricselected": "average_score", "schedule": "immediately", "timecolumn": "rolling", "value": "60"}], "notificationgroup": "email, slack sales-team"}

**Example 4: Anomaly Detection with Context**

* User Input: "We just launched the new leadership program. I'm not sure what to expect, so just alert me daily if you see any weird spikes or drops in the enrollment_count."
* supportedJson: {"Question": "What is the enrollment count for the new leadership program?", "metricsavailable": ["enrollment_count"], "conditions": ["anomalydetection"], "schedule": ["daily"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack leadership-team", "teams program-analytics"]}
* Your Output: {"type": "finished", "question": "What is the enrollment count for the new leadership program?", "alertname": "Leadership Program Enrollment Anomaly", "summary": "This alert performs daily anomaly detection on new leadership program enrollments to catch unusual spikes or drops.", "reasoning": "User's request for 'weird spikes or drops' without specific numbers indicates anomaly detection requirement.", "conditions": [{"conditionType": "anomalydetection", "metricselected": "enrollment_count", "schedule": "daily", "timecolumn": "rolling", "value": null}], "notificationgroup": "email"}

**Example 5: Text Analysis with Multiple Keywords**

* User Input: "We need to monitor feedback on the new performance management course. Can you check daily and alert the L-D-team if comments contain 'confusing' or 'too long'?"
* supportedJson: {"Question": "What is the feedback on the new performance management course?", "metricsavailable": ["feedback_comment"], "conditions": ["contains"], "schedule": ["daily"], "timecolumn": ["rolling", "default"], "notificationgroups": ["slack l-d-team", "teams learning-analytics", "email"]}
* Your Output: {"type": "finished", "question": "What is the feedback on the new performance management course?", "alertname": "Negative Course Feedback Keywords", "summary": "This alert scans performance management course feedback daily for negative keywords like 'confusing' or 'too long'.", "reasoning": "User wants to monitor qualitative feedback for specific negative keywords with daily frequency.", "conditions": [{"conditionType": "contains", "metricselected": "feedback_comment", "schedule": "daily", "timecolumn": "default", "value": "confusing"}, {"conditionType": "contains", "metricselected": "feedback_comment", "schedule": "daily", "timecolumn": "default", "value": "too long"}], "notificationgroup": "slack l-d-team"}

**Example 6: Complex Multi-Metric Alert with Mixed Conditions**

* User Input: "Send a weekly alert to leadership team if employee_turnover_rate is greater than 5%, avg_satisfaction_score is less than 3.5, time_to_hire_days exceeds 45, or if there are anomalies in productivity_score."
* supportedJson: {"Question": "What are the key weekly HR KPIs?", "metricsavailable": ["employee_turnover_rate", "avg_satisfaction_score", "time_to_hire_days", "productivity_score"], "conditions": ["greaterthan", "lessthan", "anomalydetection"], "schedule": ["weekly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email leadership-team", "slack hr-team", "powerbi hr-dashboard"]}
* Your Output: {"type": "finished", "question": "What are the key weekly HR KPIs?", "alertname": "Weekly HR KPI Health Check", "summary": "Comprehensive weekly HR health check monitoring turnover, satisfaction, hiring efficiency, and productivity anomalies.", "reasoning": "User requested weekly monitoring of four HR metrics with three different condition types including anomaly detection.", "conditions": [{"conditionType": "greaterthan", "metricselected": "employee_turnover_rate", "schedule": "weekly", "timecolumn": "rolling", "value": "5"}, {"conditionType": "lessthan", "metricselected": "avg_satisfaction_score", "schedule": "weekly", "timecolumn": "rolling", "value": "3.5"}, {"conditionType": "greaterthan", "metricselected": "time_to_hire_days", "schedule": "weekly", "timecolumn": "rolling", "value": "45"}, {"conditionType": "anomalydetection", "metricselected": "productivity_score", "schedule": "weekly", "timecolumn": "rolling", "value": null}], "notificationgroup": "email leadership-team"}

**Example 7: Clarification Needed - Vague Threshold**

* User Input: "Alert me if the number of overdue compliance tasks is high."
* supportedJson: {"Question": "How many compliance tasks are overdue?", "metricsavailable": ["overdue_compliance_tasks"], "conditions": ["greaterthan"], "schedule": ["daily", "weekly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack compliance-team", "teams legal-analytics"]}
* Your Output: I can set that up. What number should I consider to be a 'high' amount of overdue compliance tasks, and how often should I check (daily or weekly)?

**Example 8: Advanced Filter with NOT and CONTAINS Conditions**

* User Input: "Send me a weekly report of any courses where the course_status is not like 'Archived' and the course_title contains 'Legacy'."
* supportedJson: {"Question": "Find active legacy courses", "metricsavailable": ["course_status", "course_title"], "conditions": ["notlike", "contains"], "schedule": ["weekly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack content-team", "teams course-management"]}
* Your Output: {"type": "finished", "question": "Find active legacy courses", "alertname": "Active Legacy Course Report", "summary": "Weekly report identifying legacy courses that are still active (not archived) for catalog cleanup.", "reasoning": "User wants to find courses with specific title content that haven't been archived, using notlike and contains conditions.", "conditions": [{"conditionType": "notlike", "metricselected": "course_status", "schedule": "weekly", "timecolumn": "default", "value": "Archived"}, {"conditionType": "contains", "metricselected": "course_title", "schedule": "weekly", "timecolumn": "default", "value": "Legacy"}], "notificationgroup": "email"}

**Example 9: Context-Aware Multi-Turn Conversation**

* User Input: "Let's start with diversity_hiring_ratio. Alert me monthly if it's below 0.4."
* supportedJson: {"Question": "What is the diversity hiring ratio?", "metricsavailable": ["diversity_hiring_ratio"], "conditions": ["lessthan"], "schedule": ["monthly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack dei-team", "teams hr-analytics", "powerbi diversity-dashboard"]}
* Your Output: {"type": "finished", "question": "What is the diversity hiring ratio?", "alertname": "DEI Hiring Ratio Goal", "summary": "Monthly monitoring of diversity hiring ratio to ensure it meets the target threshold of 0.4.", "reasoning": "User specified monthly frequency and lessthan 0.4 condition for diversity hiring ratio monitoring.", "conditions": [{"conditionType": "lessthan", "metricselected": "diversity_hiring_ratio", "schedule": "monthly", "timecolumn": "rolling", "value": "0.4"}], "notificationgroup": "email"}

**Example 10: Comprehensive Program Health Check with Four Conditions**

* User Input: "Final alert for our 'Future Leaders' program. Send a weekly alert to powerbi dashboard if participant_satisfaction is less than 4.0, assessment_pass_rate is below 80%, voluntary_dropout_rate is greater than 10%, or if you detect any anomalies in weekly_hours_spent."
* supportedJson: {"Question": "Monitor 'Future Leaders' program health", "metricsavailable": ["participant_satisfaction", "assessment_pass_rate", "voluntary_dropout_rate", "weekly_hours_spent"], "conditions": ["lessthan", "greaterthan", "anomalydetection"], "schedule": ["weekly"], "timecolumn": ["rolling", "default"], "notificationgroups": ["email", "slack leadership-team", "teams training-analytics", "powerbi future-leaders-dashboard", "tableau program-metrics"]}
* Your Output: {"type": "finished", "question": "Monitor 'Future Leaders' program health", "alertname": "Future Leaders Program Health", "summary": "Comprehensive weekly health check for Future Leaders program monitoring satisfaction, pass rates, dropouts, and engagement anomalies.", "reasoning": "User requested complex weekly alert with four conditions covering satisfaction metrics, performance indicators, retention, and anomaly detection.", "conditions": [{"conditionType": "lessthan", "metricselected": "participant_satisfaction", "schedule": "weekly", "timecolumn": "rolling", "value": "4.0"}, {"conditionType": "lessthan", "metricselected": "assessment_pass_rate", "schedule": "weekly", "timecolumn": "rolling", "value": "80"}, {"conditionType": "greaterthan", "metricselected": "voluntary_dropout_rate", "schedule": "weekly", "timecolumn": "rolling", "value": "10"}, {"conditionType": "anomalydetection", "metricselected": "weekly_hours_spent", "schedule": "weekly", "timecolumn": "rolling", "value": null}], "notificationgroup": "powerbi future-leaders-dashboard"}
"""
        
        userprompt = f"""
User Request: {input_text}

Supported JSON for Alert Creation:
{json.dumps(supportedJson, indent=2)}

Use the full chat history and the above input to generate the correct JSON configuration or ask clarifying questions as per the rules.
"""
        return systemprompt, userprompt

    @staticmethod
    def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, 'AIAlertsService']:
        """Get existing session or create new one"""
        if session_id and session_id in sessions:
            return session_id, sessions[session_id]
        else:
            # Create new session
            new_session_id = str(uuid.uuid4())
            sessions[new_session_id] = AIAlertsService()
            return new_session_id, sessions[new_session_id]

    def clear_session(self):
        """Clear stored configs and chat history for new conversation"""
        self.stored_configs = None
        self.chatHistory = []

    def get_conversation_history_summary(self):
        """Helper method to get a summary of conversation history for debugging"""
        return {
            "total_messages": len(self.chatHistory),
            "system_messages": len([m for m in self.chatHistory if isinstance(m, SystemMessage)]),
            "human_messages": len([m for m in self.chatHistory if isinstance(m, HumanMessage)]),
            "ai_messages": len([m for m in self.chatHistory if isinstance(m, AIMessage)]),
            "conversations_count": len([m for m in self.chatHistory if isinstance(m, HumanMessage)])
        }


# FastAPI Application
app = FastAPI(title="AI Alerts Service with Compatibility", version="1.0.0")

@app.post("/ask/alertbuilder/ai")
async def ai_alert_create(alert: AlertCreate):
    try:
        # Debug: Log the incoming request
        print(f"Received request: {alert.dict()}")
        # Add this debug logging
        print(f"alert.Configs value: {alert.config}")
        print(f"alert.Config type: {type(alert.config)}")
        # Get or create session
        session_id, aiservice = AIAlertsService.get_or_create_session(alert.session_id)
        print(f"Calling createAlerts with Config: {alert.config}")
        result = await aiservice.createAlerts(alert.input, alert.config)
        return {
            "response": result,
            "session_id": session_id,
            "conversation_history": aiservice.get_conversation_history_summary(),
            "has_stored_configs": aiservice.stored_configs is not None
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing alert request: {str(e)}")

@app.post("/ask/alertbuilder/ai/debug")
async def debug_request(request_data: dict):
    """Debug endpoint to test request validation"""
    try:
        alert = AlertCreate(**request_data)
        return {
            "status": "valid",
            "parsed_data": alert.dict(),
            "configs_present": alert.config is not None
        }
    except Exception as e:
        return {
            "status": "invalid",
            "error": str(e),
            "error_details": str(e.__dict__ if hasattr(e, '__dict__') else 'No details')
        }

@app.post("/ask/alertbuilder/ai/clear-session")
async def clear_session(session_id: str):
    """Clear a specific session"""
    if session_id in sessions:
        sessions[session_id].clear_session()
        return {"message": "Session cleared successfully", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@app.get("/ask/alertbuilder/ai/sessions")
async def list_sessions():
    """List all active sessions (for debugging)"""
    return {
        "active_sessions": len(sessions),
        "session_ids": list(sessions.keys())
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Alerts Service with Compatibility"}
