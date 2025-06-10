import pandas as pd
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine
import os
from datetime import datetime
import logging
from pathlib import Path
import json
from urllib.parse import quote_plus

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PostgresUploader:
    def __init__(self, host: str, database: str, user: str, password: str, port: str = "5432"):
        """Initialize PostgreSQL connection parameters.

        Args:
            host: Database host
            database: Database name
            user: Database user
            password: Database password
            port: Database port (default: 5432)
        """
        password = "FLc&dL@M9A5Q7wI;"

        host = "unedadevpostgresql.postgres.database.azure.com"
        database = "phenom_egen_ai"
        user = "pixentia"
        encoded_password = quote_plus(password)
        
        self.connection_params = {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
            "port": port
        }
        
        # URL encode the password for SQLAlchemy connection string
        
        
        # Create SQLAlchemy engine for pandas
        self.engine = create_engine(
            f'postgresql://{user}:{encoded_password}@{host}:{port}/{database}'
        )

    def create_tables(self):
        """Create necessary tables if they don't exist."""
        try:
            with psycopg2.connect(**self.connection_params) as conn:
                with conn.cursor() as cur:
                    # Create documents table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS documents (
                            id SERIAL PRIMARY KEY,
                            document_id UUID UNIQUE,
                            source_type VARCHAR(50),
                            document_type VARCHAR(50),
                            version INTEGER,
                            content TEXT,
                            json_metadata JSONB,
                            created_at TIMESTAMP WITH TIME ZONE,
                            created_by VARCHAR(255),
                            imported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT valid_source_type CHECK (source_type IN ('gong', 'email', 'document')),
                            CONSTRAINT valid_document_type CHECK (document_type IN ('gong_transcript', 'email', 'pdf', 'docx', 'txt')),
                            CONSTRAINT valid_version CHECK (version > 0)
                        )
                    """)
                    
                    # Create training_data table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS training_data (
                            id SERIAL PRIMARY KEY,
                            full_name VARCHAR(255),
                            user_id VARCHAR(100),
                            manager_name VARCHAR(255),
                            training_type VARCHAR(100),
                            curriculum_title TEXT,
                            training_title TEXT,
                            transcript_status VARCHAR(50),
                            division VARCHAR(100),
                            position VARCHAR(100),
                            assigned_date DATE,
                            completed_date DATE,
                            due_date DATE,
                            satisfied_late BOOLEAN,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Create sum_total table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS sum_total (
                            id SERIAL PRIMARY KEY,
                            employee_name VARCHAR(255),
                            employee_id VARCHAR(100),
                            employee_email VARCHAR(255),
                            primary_domain VARCHAR(100),
                            primary_organization VARCHAR(255),
                            primary_job VARCHAR(255),
                            manager_name VARCHAR(255),
                            activity_name VARCHAR(255),
                            activity_code VARCHAR(100),
                            activity_type VARCHAR(100),
                            activity_start_date DATE,
                            activity_end_date DATE,
                            is_certification BOOLEAN,
                            training_status VARCHAR(100),
                            assignment_date DATE,
                            due_date DATE,
                            expiration_date DATE,
                            completion_date DATE,
                            satisfied_late BOOLEAN,
                            is_compliant BOOLEAN,
                            is_assigned BOOLEAN,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Create finance_flux table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS finance_flux (
                            id SERIAL PRIMARY KEY,
                            date DATE,
                            region VARCHAR(100),
                            cost_center VARCHAR(100),
                            project VARCHAR(255),
                            account VARCHAR(100),
                            source VARCHAR(100),
                            category VARCHAR(100),
                            event_type VARCHAR(100),
                            po_no VARCHAR(100),
                            transactional_value DECIMAL(15,2),
                            functional_value DECIMAL(15,2),
                            po_with_line_item VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Create air_passengers table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS air_passengers (
                            id SERIAL PRIMARY KEY,
                            month DATE,
                            passengers INTEGER,
                            year INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM month)) STORED,
                            month_number INTEGER GENERATED ALWAYS AS (EXTRACT(MONTH FROM month)) STORED,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT valid_month CHECK (month >= '1949-01-01'::date),
                            CONSTRAINT valid_passengers CHECK (passengers > 0)
                        )
                    """)
                    
                    # Create finance_demo table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS finance_demo (
                            id SERIAL PRIMARY KEY,
                            period_name VARCHAR(100),
                            country VARCHAR(100),
                            ibx VARCHAR(100),
                            parent_cost_center VARCHAR(100),
                            project VARCHAR(255),
                            account VARCHAR(100),
                            journal_source VARCHAR(100),
                            journal_category VARCHAR(100),
                            fah_event_type VARCHAR(100),
                            po_number VARCHAR(100),
                            transactional_net DECIMAL(15,2),
                            functional_net DECIMAL(15,2),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Create indices for documents
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_documents_document_id 
                        ON documents(document_id)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_documents_source_type 
                        ON documents(source_type)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_documents_document_type 
                        ON documents(document_type)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_documents_created_at 
                        ON documents(created_at)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_documents_json_metadata 
                        ON documents USING GIN (json_metadata)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_training_data_user_id 
                        ON training_data(user_id)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sum_total_employee_id 
                        ON sum_total(employee_id)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sum_total_employee_email 
                        ON sum_total(employee_email)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sum_total_activity_code 
                        ON sum_total(activity_code)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sum_total_due_date 
                        ON sum_total(due_date)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sum_total_completion_date 
                        ON sum_total(completion_date)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_flux_date 
                        ON finance_flux(date)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_flux_region 
                        ON finance_flux(region)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_flux_cost_center 
                        ON finance_flux(cost_center)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_flux_project 
                        ON finance_flux(project)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_flux_account 
                        ON finance_flux(account)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_flux_category 
                        ON finance_flux(category)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_air_passengers_month 
                        ON air_passengers(month)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_air_passengers_year 
                        ON air_passengers(year)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_air_passengers_month_number 
                        ON air_passengers(month_number)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_demo_period 
                        ON finance_demo(period_name)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_demo_country 
                        ON finance_demo(country)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_demo_ibx 
                        ON finance_demo(ibx)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_demo_cost_center 
                        ON finance_demo(parent_cost_center)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_demo_project 
                        ON finance_demo(project)
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_finance_demo_account 
                        ON finance_demo(account)
                    """)
                    
                    conn.commit()
                    logger.info("Tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            raise

    def normalize_column_name(self, col_name: str) -> str:
        """Normalize column name to match database column names.
        
        Args:
            col_name: Original column name
            
        Returns:
            Normalized column name
        """
        # Convert to lowercase and replace spaces with underscores
        normalized = col_name.lower().replace(' ', '_')
        
        # Handle common variations
        replacements = {
            'employeeid': 'employee_id',
            'employeeemail': 'employee_email',
            'primarydomain': 'primary_domain',
            'primaryorganization': 'primary_organization',
            'primaryjob': 'primary_job',
            'managername': 'manager_name',
            'activityname': 'activity_name',
            'activitycode': 'activity_code',
            'activitytype': 'activity_type',
            'activitystartdate': 'activity_start_date',
            'activityenddate': 'activity_end_date',
            'iscertification': 'is_certification',
            'trainingstatus': 'training_status',
            'assignmentdate': 'assignment_date',
            'duedate': 'due_date',
            'expirationdate': 'expiration_date',
            'completiondate': 'completion_date',
            'satisfiedlate': 'satisfied_late',
            'iscompliant': 'is_compliant',
            'isassigned': 'is_assigned'
        }
        
        return replacements.get(normalized, normalized)

    def upload_csv(self, csv_path: str, table_name: str = None):
        """Upload CSV data to PostgreSQL.

        Args:
            csv_path: Path to the CSV file
            table_name: Name of the table to upload to (if None, will be derived from filename)
        """
        try:
            logger.info(f"Reading CSV file: {csv_path}")
            
            # Determine table name from file if not provided
            if table_name is None:
                table_name = Path(csv_path).stem.lower().replace('-', '_')
            
            # Read CSV file
            df = pd.read_csv(csv_path)
            
            # Normalize column names
            df.columns = [self.normalize_column_name(col) for col in df.columns]
            
            # Print column names for debugging
            logger.info(f"Normalized columns for {table_name}: {df.columns.tolist()}")
            
            # Process based on table type
            if table_name == 'documents':
                # Convert document_id to UUID
                if 'document_id' in df.columns:
                    df['document_id'] = df['document_id'].astype(str)
                
                # Convert version to integer
                if 'version' in df.columns:
                    df['version'] = pd.to_numeric(df['version'], errors='coerce').fillna(1).astype(int)
                
                # Convert json_metadata to JSONB
                if 'json_metadata' in df.columns:
                    def process_json(x):
                        try:
                            if pd.isna(x) or x == '':
                                return None
                            if isinstance(x, str):
                                return json.loads(x)
                            return x
                        except (json.JSONDecodeError, TypeError):
                            return None
                    
                    df['json_metadata'] = df['json_metadata'].apply(process_json)
                
                # Convert created_at to timestamp with timezone
                if 'created_at' in df.columns:
                    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                
                # Add imported_at timestamp
                df['imported_at'] = datetime.now()
                
                # Clean up column names
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                
                # Convert any remaining dict objects to JSON strings
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, dict) else x)
            
            elif table_name == 'training_data':
                # Clean up column names first
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                
                # Convert date columns
                date_columns = ['assigned_date', 'completed_date', 'due_date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                
                # Convert satisfied_late to boolean
                if 'satisfied_late' in df.columns:
                    df['satisfied_late'] = df['satisfied_late'].map({'Yes': True, 'No': False, 'True': True, 'False': False})
                    df['satisfied_late'] = df['satisfied_late'].fillna(False)
                
                # Add timestamps
                df['created_at'] = datetime.now()
                df['updated_at'] = datetime.now()
                
                # Print column names for debugging
                logger.info(f"Training data columns: {df.columns.tolist()}")
                
                # Ensure all required columns exist
                required_columns = [
                    'full_name', 'user_id', 'manager_name', 'training_type',
                    'curriculum_title', 'training_title', 'transcript_status',
                    'division', 'position', 'assigned_date', 'completed_date',
                    'due_date', 'satisfied_late', 'created_at', 'updated_at'
                ]
                
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    logger.warning(f"Missing columns in training data: {missing_columns}")
                    # Add missing columns with default values
                    for col in missing_columns:
                        if col in ['created_at', 'updated_at']:
                            df[col] = datetime.now()
                        elif col == 'satisfied_late':
                            df[col] = False
                        else:
                            df[col] = None
            
            elif table_name == 'sum_total':
                # Convert date columns
                date_columns = [
                    'activity_start_date', 'activity_end_date', 'assignment_date',
                    'due_date', 'expiration_date', 'completion_date'
                ]
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                
                # Convert boolean columns
                boolean_columns = ['is_certification', 'satisfied_late', 'is_compliant', 'is_assigned']
                for col in boolean_columns:
                    if col in df.columns:
                        df[col] = df[col].map({'Yes': True, 'No': False, 'True': True, 'False': False})
                        df[col] = df[col].fillna(False)
                
                # Add timestamps
                df['created_at'] = datetime.now()
                df['updated_at'] = datetime.now()
                
                # Ensure all required columns exist
                required_columns = [
                    'employee_name', 'employee_id', 'employee_email', 'primary_domain',
                    'primary_organization', 'primary_job', 'manager_name', 'activity_name',
                    'activity_code', 'activity_type', 'activity_start_date', 'activity_end_date',
                    'is_certification', 'training_status', 'assignment_date', 'due_date',
                    'expiration_date', 'completion_date', 'satisfied_late', 'is_compliant',
                    'is_assigned', 'created_at', 'updated_at'
                ]
                
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    logger.warning(f"Missing columns in sum_total: {missing_columns}")
                    # Add missing columns with default values
                    for col in missing_columns:
                        if col in ['created_at', 'updated_at']:
                            df[col] = datetime.now()
                        elif col in boolean_columns:
                            df[col] = False
                        else:
                            df[col] = None
            
            elif table_name == 'finance_flux':
                # Convert date column
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                
                # Convert numeric columns
                numeric_columns = ['transactional_value', 'functional_value']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Clean up column names
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            
            elif table_name == 'air_passengers':
                # Convert month to date
                if 'month' in df.columns:
                    df['month'] = pd.to_datetime(df['month'], format='%Y-%m', errors='coerce')
                
                # Convert passengers to integer
                if 'passengers' in df.columns:
                    df['passengers'] = pd.to_numeric(df['passengers'], errors='coerce').astype('Int64')
                
                # Clean up column names
                df.columns = [col.lower().replace('#', '').replace(' ', '_') for col in df.columns]
            
            elif table_name == 'finance_demo':
                # Convert numeric columns
                numeric_columns = ['transactional_net', 'functional_net']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Clean up column names
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            
            logger.info(f"Uploading {len(df)} rows to {table_name}")
            
            # Upload to PostgreSQL
            df.to_sql(
                table_name,
                self.engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )
            
            logger.info(f"Upload to {table_name} completed successfully")
            print(f"Upload to {table_name} completed successfully")   
            
        except Exception as e:
            logger.error(f"Error uploading CSV {csv_path} to {table_name}: {str(e)}")
            raise

    def drop_and_recreate_tables(self):
        """Drop and recreate all tables."""
        try:
            with psycopg2.connect(**self.connection_params) as conn:
                with conn.cursor() as cur:
                    # Drop tables in reverse order of dependencies
                    tables = [
                        #'air_passengers',
                        #'finance_demo',
                        #'finance_flux',
                        'sum_total',
                        'training_data',
                        'documents'
                    ]
                    
                    for table in tables:
                        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                        logger.info(f"Dropped table {table}")
                    
                    conn.commit()
                    logger.info("All tables dropped successfully")
                    
                    # Recreate tables
                    self.create_tables()
                    logger.info("All tables recreated successfully")
                    
        except Exception as e:
            logger.error(f"Error dropping and recreating tables: {str(e)}")
            raise

def main():
    # Get database credentials from environment variables
    db_host = os.getenv("POSTGRES_HOST","unedadevpostgresql.postgres.database.azure.com")
    db_name = os.getenv("POSTGRES_DB","phenom_egen_ai")
    db_user = os.getenv("POSTGRES_USER","pixentia")
    db_password = os.getenv("POSTGRES_PASSWORD","FLc&dL@M9A5Q7wI;")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    
    if not all([db_host, db_name, db_user, db_password]):
        raise ValueError("Missing required database credentials in environment variables")
    
    # Initialize uploader
    uploader = PostgresUploader(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
        port=db_port
    )
    
    """
    # Drop and recreate tables
    try:
        logger.info("Dropping and recreating database tables...")
        uploader.drop_and_recreate_tables()
        logger.info("Database tables recreated successfully")
    except Exception as e:
        logger.error(f"Failed to recreate tables: {str(e)}")
        return
    """
    # Define input directory
    input_dir = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/inputs"
    
    # Map of CSV files to their table names
    csv_mappings = {
        #'documents.csv': 'documents',
        'CSODTrainingDataset.csv': 'training_data',
        'SumtotalDataSet.csv': 'sum_total',
        #'bv_finance_flux_final.csv': 'finance_flux',
        #'Finance_demo_BV.csv': 'finance_demo',
        #'AirPassengers.csv': 'air_passengers'
    }
    
    # Process each CSV file sequentially
    for csv_file, table_name in csv_mappings.items():
        csv_path = os.path.join(input_dir, csv_file)
        
        if not os.path.exists(csv_path):
            logger.warning(f"File not found: {csv_path}")
            continue
            
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {csv_file} for table {table_name}...")
        logger.info(f"{'='*50}")
        
        try:
            # Verify CSV file is readable
            try:
                with open(csv_path, 'r') as f:
                    # Read first line to verify file is readable
                    header = f.readline().strip()
                    if not header:
                        raise ValueError("CSV file is empty")
                    logger.info(f"CSV header: {header}")
            except Exception as e:
                logger.error(f"Error reading CSV file {csv_file}: {str(e)}")
                continue
            
            # Upload CSV data
            uploader.upload_csv(csv_path, table_name)
            
            # Verify data was uploaded
            try:
                with psycopg2.connect(**uploader.connection_params) as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cur.fetchone()[0]
                        logger.info(f"Successfully uploaded {count} rows to {table_name}")
            except Exception as e:
                logger.error(f"Error verifying upload for {table_name}: {str(e)}")
                continue
                
            logger.info(f"Successfully processed {csv_file}")
            
        except Exception as e:
            logger.error(f"Failed to process {csv_file}: {str(e)}")
            logger.error("Continuing with next file...")
            continue
        
        logger.info(f"Completed processing {csv_file}\n")

if __name__ == "__main__":
    main() 