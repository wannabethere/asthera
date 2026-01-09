"""
Example API call to validate an alert condition using the alert data provided.

This script demonstrates how to call the /alerts/validate-condition endpoint
with the ProposedAlertConditionValidationRequest format.
"""

import requests
import json
from typing import Dict, Any

# API endpoint (adjust the base URL as needed)
BASE_URL = "http://localhost:8000"  # Update with your actual server URL
ENDPOINT = f"{BASE_URL}/alerts/validate-condition"

# Alert data extracted from the provided response
alert_data = {
    "sql": "SELECT SUM(criticalCount) AS total_critical, SUM(highCount) AS total_high, SUM(overdueCount) AS total_overdue FROM ComplianceRisk_Daily;",
    "proposed_alert": {
        "metric": {
            "domain": "ComplianceRisk",
            "dataset_id": "ComplianceRisk_Daily",
            "measure": "total_critical",
            "aggregation": "SUM",
            "resolution": "Daily",
            "filters": [],
            "drilldown_dimensions": []
        },
        "conditions": [
            {
                "condition_type": "threshold_value",
                "threshold_type": "based_on_value",
                "operator": ">",
                "value": 50
            }
        ],
        "notification": {
            "schedule_type": "daily",
            "metric_name": "Critical Compliance Risk Alert",
            "email_addresses": [
                "admin@company.com"
            ],
            "subject": "Alert: Critical Compliance Risk Threshold Exceeded",
            "email_message": "The total critical compliance risk count has exceeded the threshold of 50.",
            "include_feed_report": True,
            "custom_schedule": None
        },
        "column_selection": {
            "included": [
                "total_critical",
                "total_high",
                "total_overdue"
            ],
            "excluded": []
        }
    },
    "project_id": "string",
    "condition_index": 0,  # Validate the first condition (index 0)
    "metric_column": None,  # Will use metric.measure ("total_critical") if None
    "use_cache": True,
    "overall_condition_logic": "any_met",
    "business_context": "Calculate estimated financial exposure from compliance violations"
}

def validate_condition():
    """Call the validate-condition endpoint"""
    try:
        print("Calling /alerts/validate-condition endpoint...")
        print(f"URL: {ENDPOINT}")
        print("\nRequest payload:")
        print(json.dumps(alert_data, indent=2))
        print("\n" + "="*80 + "\n")
        
        response = requests.post(
            ENDPOINT,
            json=alert_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print("\nResponse:")
        
        if response.status_code == 200:
            result = response.json()
            print(json.dumps(result, indent=2))
            
            # Print summary
            print("\n" + "="*80)
            print("Validation Summary:")
            print(f"  Is Valid: {result.get('is_valid')}")
            print(f"  Current Value: {result.get('current_value')}")
            print(f"  Threshold Value: {result.get('threshold_value')}")
            print(f"  Condition Met: {result.get('condition_met')}")
            if result.get('error_message'):
                print(f"  Error: {result.get('error_message')}")
        else:
            print(f"Error: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    validate_condition()
