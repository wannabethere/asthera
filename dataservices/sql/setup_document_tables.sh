#!/bin/bash

# =====================================================
# Document Tables Setup Script
# =====================================================
# This script sets up the document management tables
# Run this script to create the necessary database tables

set -e  # Exit on any error

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-genieml}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if PostgreSQL is available
check_postgres() {
    print_status "Checking PostgreSQL connection..."
    
    if command -v psql &> /dev/null; then
        print_success "psql command found"
    else
        print_error "psql command not found. Please install PostgreSQL client tools."
        exit 1
    fi
    
    # Test connection
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
        print_success "PostgreSQL connection successful"
    else
        print_error "Cannot connect to PostgreSQL. Please check your connection parameters."
        print_status "Connection details:"
        print_status "  Host: $DB_HOST"
        print_status "  Port: $DB_PORT"
        print_status "  Database: $DB_NAME"
        print_status "  User: $DB_USER"
        exit 1
    fi
}

# Function to create tables
create_tables() {
    print_status "Creating document tables..."
    
    if [ -f "create_document_tables.sql" ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f create_document_tables.sql
        print_success "Document tables created successfully"
    else
        print_error "create_document_tables.sql not found in current directory"
        exit 1
    fi
}

# Function to run migration if needed
run_migration() {
    if [ "$1" = "--migrate" ]; then
        print_status "Running migration script..."
        
        if [ -f "migrate_document_tables.sql" ]; then
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f migrate_document_tables.sql
            print_success "Migration completed successfully"
        else
            print_error "migrate_document_tables.sql not found in current directory"
            exit 1
        fi
    fi
}

# Function to verify tables were created
verify_tables() {
    print_status "Verifying table creation..."
    
    TABLES=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('doc_versions', 'doc_insight_versions')
        ORDER BY table_name;
    ")
    
    if echo "$TABLES" | grep -q "doc_versions" && echo "$TABLES" | grep -q "doc_insight_versions"; then
        print_success "All required tables created successfully"
        print_status "Created tables:"
        echo "$TABLES" | while read -r table; do
            if [ -n "$table" ]; then
                print_status "  - $table"
            fi
        done
    else
        print_error "Some tables were not created successfully"
        exit 1
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --migrate              Run migration script for existing databases"
    echo "  --help, -h             Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  DB_HOST                PostgreSQL host (default: localhost)"
    echo "  DB_PORT                PostgreSQL port (default: 5432)"
    echo "  DB_NAME                Database name (default: genieml)"
    echo "  DB_USER                Database user (default: postgres)"
    echo "  DB_PASSWORD            Database password"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Create tables with default settings"
    echo "  $0 --migrate                         # Run migration for existing database"
    echo "  DB_PASSWORD=mypass $0                # Set password via environment variable"
    echo "  DB_HOST=remote $0 --migrate          # Connect to remote host and migrate"
}

# Main execution
main() {
    print_status "Starting Document Tables Setup"
    print_status "================================="
    
    # Check for help flag
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        show_usage
        exit 0
    fi
    
    # Check PostgreSQL connection
    check_postgres
    
    # Create tables
    create_tables
    
    # Run migration if requested
    run_migration "$1"
    
    # Verify tables
    verify_tables
    
    print_success "Document tables setup completed successfully!"
    print_status ""
    print_status "Next steps:"
    print_status "1. Update your application configuration to use the new tables"
    print_status "2. Test the DocumentIngestionService with the new schema"
    print_status "3. Run sample queries to verify everything works correctly"
    print_status ""
    print_status "Sample queries to test:"
    print_status "  SELECT * FROM latest_document_versions LIMIT 5;"
    print_status "  SELECT * FROM documents_with_insights LIMIT 5;"
    print_status "  SELECT * FROM search_documents_by_content('revenue', 'domain_123', 'financial_report', 5);"
}

# Run main function with all arguments
main "$@"
