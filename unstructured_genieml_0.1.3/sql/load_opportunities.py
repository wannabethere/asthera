import os

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg import sql

# Load environment variables
load_dotenv()

def load_opportunities_to_postgres(csv_path):
    print(f"Loading opportunities from {csv_path} to PostgreSQL")
    # Read the CSV file
    df = pd.read_csv(csv_path)

    # Convert CampaignId from float to string, handling NaN values
    df['CampaignId'] = df['CampaignId'].fillna('').astype(str)

    # Set column names to match SQL table
    df.columns = ["id", "name", "stage_name", "close_date", "amount", "probability", "forecast_category", "expected_revenue", "owner_id", "account_id", "type", "lead_source", "created_date", "last_modified_date", "next_step", "is_closed", "is_won", "campaign_id"]

    # Connect to PostgreSQL
    connection_params = {
        "host": os.getenv('DB_HOST'),
        "port": os.getenv('DB_PORT'),
        "dbname": os.getenv('DB_NAME'),
        "user": os.getenv('DB_USER'),
        "password": os.getenv('DB_PASSWORD').replace("$$", "$"),
    }
    conn: psycopg.Connection = psycopg.connect(**connection_params)

    # Create a cursor
    cur: psycopg.Cursor = conn.cursor()

    # Insert the data
    try:
        # Create a single VALUES statement for all rows
        values_list = []
        for _, row in df.iterrows():
            values_list.append(sql.SQL("({})").format(
                sql.SQL(', ').join([sql.Literal(val) for val in row.tolist()])
            ))
        insert_query = sql.SQL("INSERT INTO sfdc_opportunities ({}) VALUES {}").format(
            sql.SQL(', ').join(map(sql.Identifier, df.columns)),
            sql.SQL(', ').join(values_list)
        )
        print(f"Insert query: {insert_query}")
        cur.execute(insert_query)
    except Exception as e:
        print(f"Error inserting data: {e}")
        raise

    # Commit the transaction
    conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    print(f"Successfully loaded {len(df)} records into the opportunities table")

if __name__ == "__main__":
    csv_path = "/Users/griff/Code/Repos/Github/Tellius/kaiya-unstructureddata-agentic/example_data/sfdc/mock_opportunities_with_customers.csv"
    load_opportunities_to_postgres(csv_path)
