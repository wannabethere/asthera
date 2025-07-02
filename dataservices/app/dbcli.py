
# ============================================================================
# CLI INTERFACE
# ============================================================================

class CLIInterface:
    """Command-line interface for the service"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        # Call the new function to ensure tables exist
        create_db_tables()
    
    async def interactive_session(self, project_id: str):
        """Start interactive session for creating definitions"""
        print("🚀 LLM Definition Service - Interactive Mode")
        print("=" * 50)
        
        # Create a session just for this operation
        session = SessionLocal()
        try:
            service = LLMDefinitionService(
                session=session,
                openai_api_key=self.config.openai_api_key,
                mcp_server_url=self.config.mcp_server_url,
                project_id=project_id
            )
            
            while True:
                # ... (no change inside the loop)
                print("\nWhat would you like to create?")
                print("1. Metric")
                print("2. View")
                print("3. Calculated Column")
                print("4. Exit")
                
                choice = input("Enter your choice (1-4): ").strip()
                
                if choice == "1":
                    await service.interactive_definition_creation(DefinitionType.METRIC)
                elif choice == "2":
                    await service.interactive_definition_creation(DefinitionType.VIEW)
                elif choice == "3":
                    await service.interactive_definition_creation(DefinitionType.CALCULATED_COLUMN)
                elif choice == "4":
                    print("Goodbye! 👋")
                    break
                else:
                    print("Invalid choice. Please try again.")
        
        finally:
            # Always close the session when done
            session.close()
    
    async def create_sample_project(self, project_id: str = "sample_project"):
        """Create a sample project with test data"""
        # Create a session just for this operation
        session = SessionLocal()
        try:
            project_manager = ProjectManager(session)
            
            # Create project
            project = project_manager.create_project(
                project_id=project_id,
                display_name="Sample Training Project",
                description="Sample project for testing LLM definition service",
                created_by="system"
            )
            
            print(f"✅ Created sample project: {project_id}")
            print(f"Version: {project.version_string}")
            
            return project_id
            
        finally:
            # Always close the session when done
            session.close()

# ============================================================================
# EXAMPLE USAGE AND TESTING
# ============================================================================

async def run_examples():
    """Run example usage scenarios"""
    config = ServiceConfig.from_env()
    cli = CLIInterface(config)
    
    # Create sample project
    project_id = await cli.create_sample_project("example_project")
    
    # Example API requests you could make:
    examples = {
        "metric_example": {
            "definition_type": "metric",
            "name": "division_completion_rate",
            "description": "Calculate completion rate by division",
            "sql": "SELECT Division, COUNT(CASE WHEN Transcript_Status = 'Satisfied' THEN 1 END) * 100.0 / COUNT(*) as completion_rate FROM csod_training_records GROUP BY Division"
        },
        "view_example": {
            "definition_type": "view",
            "name": "training_dashboard",
            "description": "Create a comprehensive training dashboard view",
            "additional_context": {
                "purpose": "executive_reporting",
                "refresh_frequency": "daily"
            }
        },
        "calculated_column_example": {
            "definition_type": "calculated_column",
            "name": "days_to_complete",
            "description": "Calculate the number of days it took to complete training",
            "sql": "DATEDIFF(day, Assigned_Date, Completed_Date)"
        }
    }
    
    print("\n📝 Example API requests:")
    for name, example in examples.items():
        print(f"\n{name}:")
        print(f"POST /projects/{project_id}/definitions")
        print(json.dumps(example, indent=2))


# ============================================================================
# MAIN ENTRY POINTS
# ============================================================================

def main_api():
    """Main entry point for API server"""
    import uvicorn
    
    config = ServiceConfig.from_env()
    app = create_app(config)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=config.log_level.lower()
    )


async def main_cli():
    """Main entry point for CLI interface"""
    import sys
    
    config = ServiceConfig.from_env()
    cli = CLIInterface(config)
    
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        await cli.interactive_session(project_id)
    else:
        print("Usage: python service_configuration.py <project_id>")
        print("Or use 'sample' to create a sample project")
        
        if input("Create sample project? (y/n): ").lower().startswith('y'):
            project_id = await cli.create_sample_project()
            await cli.interactive_session(project_id)


if __name__ == "__main__":
    import sys
    
    if "--api" in sys.argv:
        main_api()
    elif "--examples" in sys.argv:
        asyncio.run(run_examples())
    else:
        asyncio.run(main_cli())