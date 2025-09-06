# 📦 Python Packages for Jinja Templating System

## 🔧 Core Requirements

### Essential Packages (Always Required)
```bash
# Templating engine - the heart of our system
pip install jinja2>=3.1.0

# Data manipulation - required by all database templates
pip install pandas>=1.5.0
```

## 🗄️ Database-Specific Requirements

### PostgreSQL Support
```bash
# SQLAlchemy - database abstraction layer
pip install sqlalchemy>=2.0.0

# PostgreSQL adapter - most popular and reliable
pip install psycopg2-binary>=2.9.0
# Alternative: pip install psycopg2  # if you want to compile from source
```

### Trino Support  
```bash
# Trino Python client
pip install trino>=0.320.0
```

### Optional Database Support
```bash
# MySQL support (if you create MySQL templates)
pip install pymysql>=1.0.0

# SQLite support (built-in, but enhanced driver)
pip install pysqlite3-binary  # Optional: better performance

# MongoDB support (if creating NoSQL templates)
pip install pymongo>=4.0.0

# Redis support (if creating Redis templates)  
pip install redis>=4.0.0
```

## ✨ Development & Enhancement Packages

### Security & Configuration
```bash
# Environment variable management - HIGHLY RECOMMENDED for production
pip install python-dotenv>=1.0.0

# Advanced data validation - upgrade from basic dict validation
pip install pydantic>=2.0.0
```

### CLI & User Experience
```bash
# Rich terminal output - makes console output beautiful
pip install rich>=13.0.0

# Modern CLI framework - if building command line tools
pip install typer>=0.9.0
# Alternative: pip install click>=8.0.0
```

### Testing & Quality
```bash
# Testing framework
pip install pytest>=7.0.0
pip install pytest-cov>=4.0.0  # Coverage reporting

# Code formatting and linting
pip install black>=23.0.0      # Code formatter
pip install isort>=5.12.0      # Import sorter
pip install flake8>=6.0.0      # Linting
pip install mypy>=1.0.0        # Type checking
```

### Performance & Monitoring
```bash
# Memory profiling - useful for large template generation
pip install memory-profiler>=0.60.0

# Performance timing
pip install line-profiler>=4.0.0
```

## 📋 Complete Installation Commands

### Minimal Installation (Core Functionality)
```bash
pip install jinja2>=3.1.0 pandas>=1.5.0
```

### Basic Database Support
```bash
pip install jinja2>=3.1.0 pandas>=1.5.0 sqlalchemy>=2.0.0 psycopg2-binary>=2.9.0 trino>=0.320.0
```

### Recommended Production Setup
```bash
pip install jinja2>=3.1.0 pandas>=1.5.0 sqlalchemy>=2.0.0 psycopg2-binary>=2.9.0 \
            trino>=0.320.0 python-dotenv>=1.0.0 pydantic>=2.0.0 rich>=13.0.0
```

### Full Development Environment
```bash
pip install jinja2>=3.1.0 pandas>=1.5.0 sqlalchemy>=2.0.0 psycopg2-binary>=2.9.0 \
            trino>=0.320.0 python-dotenv>=1.0.0 pydantic>=2.0.0 rich>=13.0.0 \
            typer>=0.9.0 pytest>=7.0.0 pytest-cov>=4.0.0 black>=23.0.0 \
            isort>=5.12.0 flake8>=6.0.0 mypy>=1.0.0
```

## 📄 requirements.txt File

Create a `requirements.txt` file for your project:

```text
# Core templating system
jinja2>=3.1.0
pandas>=1.5.0

# Database connectors
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
trino>=0.320.0

# Configuration and security
python-dotenv>=1.0.0

# Enhanced validation (optional but recommended)
pydantic>=2.0.0

# Better console output (optional but recommended)
rich>=13.0.0
```

## 🚀 Alternative Installation Methods

### Using pip with requirements.txt
```bash
pip install -r requirements.txt
```

### Using Poetry (Recommended for new projects)
```bash
# Initialize new project
poetry new jinja-templates
cd jinja-templates

# Add dependencies
poetry add jinja2 pandas sqlalchemy psycopg2-binary trino python-dotenv rich

# Development dependencies
poetry add --group dev pytest black isort flake8 mypy

# Install all dependencies
poetry install
```

### Using conda (If you prefer conda)
```bash
# Core packages (most available on conda-forge)
conda install -c conda-forge jinja2 pandas sqlalchemy psycopg2 python-dotenv rich

# Trino might need pip
pip install trino
```

## 🔍 Package Details & Why We Need Them

### Core System Packages
- **jinja2**: Template engine that powers our code generation
- **pandas**: DataFrame operations used in all generated database scripts

### Database Connectors
- **sqlalchemy**: Database abstraction layer, connection pooling, SQL generation
- **psycopg2-binary**: PostgreSQL adapter - pre-compiled for easy installation
- **trino**: Official Trino Python client for distributed SQL queries

### Enhancement Packages  
- **python-dotenv**: Load environment variables from .env files (security best practice)
- **pydantic**: Advanced data validation with type hints (upgrade from basic dict validation)
- **rich**: Beautiful terminal output with colors, tables, and progress bars

### Development Tools
- **pytest**: Modern testing framework
- **black**: Uncompromising code formatter
- **mypy**: Static type checking
- **isort**: Sorts imports automatically

## ⚠️ Common Installation Issues & Solutions

### PostgreSQL Connection Issues
```bash
# If psycopg2-binary fails, try:
pip install psycopg2

# On Ubuntu/Debian, you might need:
sudo apt-get install libpq-dev python3-dev

# On macOS with Homebrew:
brew install postgresql
```

### Trino Connection Issues
```bash
# Make sure you have the latest version
pip install --upgrade trino

# If authentication issues, you might also need:
pip install requests-kerberos  # For Kerberos auth
pip install requests-oauthlib  # For OAuth
```

### Alternative PostgreSQL Adapters
```bash
# If psycopg2 doesn't work, try asyncpg (async only)
pip install asyncpg

# Or pg8000 (pure Python)
pip install pg8000
```

## 🎯 Version Compatibility

Our system is compatible with:
- **Python**: 3.8+ (3.9+ recommended)
- **Jinja2**: 3.0+ (3.1+ recommended for latest features)
- **Pandas**: 1.3+ (2.0+ recommended for better performance)
- **SQLAlchemy**: 1.4+ (2.0+ recommended for modern async support)

## 🔄 Upgrade Commands

To upgrade all packages to latest versions:
```bash
pip install --upgrade jinja2 pandas sqlalchemy psycopg2-binary trino python-dotenv rich
```

## 🧪 Testing Your Installation

Create a simple test script to verify all packages work:

```python
#!/usr/bin/env python3
"""Test script to verify all required packages are installed correctly."""

def test_imports():
    try:
        import jinja2
        print(f"✅ Jinja2 {jinja2.__version__}")
        
        import pandas as pd
        print(f"✅ Pandas {pd.__version__}")
        
        import sqlalchemy
        print(f"✅ SQLAlchemy {sqlalchemy.__version__}")
        
        import psycopg2
        print(f"✅ Psycopg2 {psycopg2.__version__}")
        
        import trino
        print(f"✅ Trino {trino.__version__}")
        
        # Optional packages
        try:
            import dotenv
            print(f"✅ Python-dotenv {dotenv.__version__}")
        except ImportError:
            print("⚠️  Python-dotenv not installed (optional)")
            
        try:
            import rich
            print(f"✅ Rich {rich.__version__}")
        except ImportError:
            print("⚠️  Rich not installed (optional)")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🧪 Testing Jinja Template System Dependencies")
    print("=" * 50)
    
    if test_imports():
        print("\n🎉 All core dependencies installed successfully!")
    else:
        print("\n💥 Some dependencies are missing. Please install them.")
```

Save this as `test_dependencies.py` and run:
```bash
python test_dependencies.py
```