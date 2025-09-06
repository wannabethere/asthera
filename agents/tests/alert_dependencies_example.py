"""
Example showing how the alert service dependencies work

This demonstrates how the dependency injection system works with the alert services.
"""

from fastapi import FastAPI, Depends
from app.core.dependencies import get_alert_service, get_alert_compatibility_service
from app.services.writers.alert_service import AlertCreate, Configs

# Example FastAPI app showing dependency usage
app = FastAPI()

@app.get("/example/alert-service")
async def example_alert_service_endpoint(
    alert_service = Depends(get_alert_service)
):
    """Example endpoint using alert service dependency."""
    return {
        "message": "Alert service is available",
        "service_type": type(alert_service).__name__,
        "pipeline_container_available": hasattr(alert_service, '_pipeline_container')
    }

@app.get("/example/alert-compatibility-service")
async def example_alert_compatibility_endpoint(
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Example endpoint using alert compatibility service dependency."""
    return {
        "message": "Alert compatibility service is available",
        "service_type": type(compatibility_service).__name__,
        "underlying_service_available": compatibility_service.get_underlying_alert_service() is not None,
        "compatibility_wrapper_available": compatibility_service.get_compatibility_wrapper() is not None
    }

@app.post("/example/process-alert")
async def example_process_alert(
    alert_create: AlertCreate,
    compatibility_service = Depends(get_alert_compatibility_service)
):
    """Example endpoint processing an alert using dependency injection."""
    try:
        result = await compatibility_service.process_alert_create(alert_create)
        return {
            "success": True,
            "alert_name": result.alertname,
            "service_created": result.service_created,
            "project_id": result.project_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Example of how dependencies are resolved
def demonstrate_dependency_resolution():
    """Demonstrate how FastAPI dependency injection works."""
    
    print("=== Alert Service Dependencies ===")
    print("1. get_alert_service() - Returns app.state.alert_service")
    print("2. get_alert_compatibility_service() - Returns app.state.alert_compatibility_service")
    print()
    print("=== Service Initialization Flow ===")
    print("1. main.py calls get_dependencies()")
    print("2. main.py calls sql_container.initialize_services(app.state)")
    print("3. Service container creates AlertService and AlertCompatibilityService")
    print("4. Services are stored in app.state.alert_service and app.state.alert_compatibility_service")
    print("5. Dependencies can access services from app state")
    print()
    print("=== Usage in Endpoints ===")
    print("- Use Depends(get_alert_service) for native alert functionality")
    print("- Use Depends(get_alert_compatibility_service) for main.py compatibility")
    print("- FastAPI automatically injects the services when endpoints are called")
    print()
    print("=== Benefits ===")
    print("- Clean separation of concerns")
    print("- Consistent with other services in the application")
    print("- Easy to test and mock")
    print("- Automatic dependency resolution")

if __name__ == "__main__":
    demonstrate_dependency_resolution()
