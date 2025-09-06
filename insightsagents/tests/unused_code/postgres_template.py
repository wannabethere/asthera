import pandas as pd
from sqlalchemy import create_engine

# --- Step 1: Configure your PostgreSQL connection ---
# It's recommended to use Databricks secrets for sensitive information like passwords.
# Replace the placeholder values with your actual PostgreSQL connection information.
POSTGRES_HOST = "your-postgres-host.com"
POSTGRES_PORT = 5432
POSTGRES_DBNAME = "your-database"
POSTGRES_USER = "your-user"
POSTGRES_PASSWORD = "your-password" # Use Databricks secrets in a real-world scenario

# --- Step 2: Create a SQLAlchemy engine for PostgreSQL ---
# The URL format for PostgreSQL using psycopg2 is:
# postgresql+psycopg2://user:password@host:port/database
try:
    connection_string = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
        f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"
    )
    engine = create_engine(connection_string)
    print("Successfully created PostgreSQL connection engine.")
except Exception as e:
    print(f"Error creating PostgreSQL connection engine: {e}")
    # Handle the connection error appropriately

# --- Step 3: Define your SQL query and read into a pandas DataFrame ---
# Replace `your_table` with the name of the table you want to query.
query = "DUMMY_QUERY PLACE HOLDER"

try:
    # Use pandas.read_sql_query() to execute the query and return a DataFrame.
    # The `engine` object handles the connection to PostgreSQL.
    pandas_df = pd.read_sql_query(query, engine)
    
    print("\nSuccessfully fetched data and created a pandas DataFrame.")
    print("\nDisplaying the first 5 rows of the DataFrame:")
    print(pandas_df.head())
    
    print("\nDisplaying the DataFrame info:")
    print(pandas_df.info())

except Exception as e:
    print(f"Error executing query or creating DataFrame: {e}")
finally:
    # Always dispose of the engine to close the database connection.
    if 'engine' in locals():
        engine.dispose()
