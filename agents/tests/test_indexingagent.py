#!/usr/bin/env python3
"""
LLM-Powered Analytics Workflow Setup Script

This script helps users set up the LLM-powered analytics workflow environment
and validates all dependencies are properly installed.
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def print_header():
    """Print setup header"""
    print("🤖 LLM-POWERED ANALYTICS WORKFLOW SETUP")
    print("=" * 50)
    print("Setting up your AI-powered analytics environment...")
    print()


def check_python_version():
    """Check Python version compatibility"""
    print("🐍 Checking Python version...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True


def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True, check=True)
        
        print("✅ Dependencies installed successfully")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print(f"   Output: {e.stdout}")
        print(f"   Error: {e.stderr}")
        return False


def check_openai_key():
    """Check OpenAI API key"""
    print("\n🔑 Checking OpenAI API key...")
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  OpenAI API key not found in environment")
        print("   Please set your API key:")
        print("   export OPENAI_API_KEY='your-key-here'")
        print("   Or create a .env file with: OPENAI_API_KEY=your-key-here")
        print("   Get an API key at: https://platform.openai.com/api-keys")
        return False
    
    print(f"✅ OpenAI API key found: {api_key[:10]}...")
    return True


def test_openai_connection():
    """Test OpenAI API connection"""
    print("\n🔗 Testing OpenAI connection...")
    
    try:
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.1,
            timeout=30
        )
        
        # Simple test call
        response = llm.invoke("Say 'Connection test successful'")
        
        if "successful" in response.content.lower():
            print("✅ OpenAI connection successful")
            return True
        else:
            print("⚠️  OpenAI response unexpected")
            return False
    
    except Exception as e:
        print(f"❌ OpenAI connection failed: {e}")
        print("   Check your API key and internet connection")
        return False


def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating project directories...")
    
    directories = [
        "sample_data",
        "generated_projects",
        "demo_data",
        "demo_output"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"   ✅ {directory}/")
    
    return True


def create_sample_config():
    """Create sample configuration file"""
    print("\n⚙️  Creating sample configuration...")
    
    config = {
        "project_settings": {
            "project_name": "Sample LLM Analytics Project",
            "business_purpose": "Demonstrate LLM-powered data analysis and intelligent insights generation",
            "additional_context": "Focus on showcasing AI-driven pattern detection and automated business intelligence",
            "output_directory": "./generated_projects"
        },
        "data_sources": {
            "csv_file_path": "./sample_data/data.csv",
            "questions_file_path": "./sample_data/questions.txt",
            "max_questions": 10
        },
        "llm_settings": {
            "model": "gpt-4",
            "temperature": 0.1,
            "max_retries": 3,
            "timeout": 120
        },
        "workflow_options": {
            "enable_domain_inference": True,
            "enable_entity_extraction": True,
            "enable_intelligent_sql": True,
            "enable_automated_documentation": True,
            "generate_additional_questions": True
        }
    }
    
    config_path = Path("sample_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Sample configuration created: {config_path}")
    return True


def create_sample_env():
    """Create sample .env file"""
    print("\n🔧 Creating sample .env file...")
    
    env_content = """# LLM-Powered Analytics Workflow Environment Variables
# Copy this to .env and add your actual values

# OpenAI API Key (required)
OPENAI_API_KEY=your-openai-api-key-here

# Optional: Default model to use
DEFAULT_LLM_MODEL=gpt-4

# Optional: Default temperature
DEFAULT_LLM_TEMPERATURE=0.1

# Optional: Cost control
MAX_QUESTIONS_DEFAULT=15
"""
    
    env_example_path = Path(".env.example")
    with open(env_example_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"✅ Sample environment file created: {env_example_path}")
    print("   Copy to .env and add your OpenAI API key")
    return True


def validate_installation():
    """Validate the installation"""
    print("\n✅ Validating installation...")
    
    # Check key files exist
    required_files = [
        "csv_analysis_agent.py",
        "mdl_generation_agent.py", 
        "sql_pairs_agent.py",
        "project_generation_agent.py",
        "analytics_workflow.py",
        "cli_interface.py",
        "demo.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ All core files present")
    
    # Test imports
    try:
        import pandas
        import langchain
        import langchain_openai
        print("✅ All dependencies importable")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    return True


def print_next_steps():
    """Print next steps for the user"""
    print("\n🎯 SETUP COMPLETE!")
    print("=" * 30)
    print()
    print("🚀 Next Steps:")
    print("1. Set your OpenAI API key:")
    print("   export OPENAI_API_KEY='your-key-here'")
    print()
    print("2. Run the demo to see AI in action:")
    print("   python demo.py")
    print()
    print("3. Or start with your own data:")
    print("   python cli_interface.py --create-config my_config.json")
    print("   # Edit my_config.json with your settings")
    print("   python cli_interface.py --config my_config.json")
    print()
    print("4. Generate AI-powered sample questions:")
    print("   python cli_interface.py --sample-questions questions.txt --domain sales")
    print()
    print("💡 Tips:")
    print("   • Start with the demo to understand capabilities")
    print("   • Use --estimate-cost to preview API costs")
    print("   • Check README.md for comprehensive documentation")
    print("   • Use --verbose flag for detailed output")
    print()
    print("🤖 Ready to experience AI-powered analytics!")


def main():
    """Main setup function"""
    print_header()
    
    success = True
    
    # Run setup steps
    if not check_python_version():
        success = False
    
    if success and not install_dependencies():
        success = False
    
    if success:
        create_directories()
        create_sample_config()
        create_sample_env()
    
    if success and not check_openai_key():
        print("⚠️  Continue setup, but you'll need an API key to run the workflow")
    
    if success and os.getenv('OPENAI_API_KEY'):
        if not test_openai_connection():
            print("⚠️  API key issues detected, but setup will continue")
    
    if success and not validate_installation():
        success = False
    
    if success:
        print_next_steps()
    else:
        print("\n❌ Setup encountered issues")
        print("   Please resolve the errors above and try again")
        sys.exit(1)


if __name__ == "__main__":
    main()