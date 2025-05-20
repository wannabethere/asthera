import os
import psycopg2

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/genieml")
SQL_FILE = os.path.join(os.path.dirname(__file__), "init_db.sql")

def run_sql_script():
    with open(SQL_FILE, "r") as f:
        sql = f.read()
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Database initialized successfully.")
    finally:
        conn.close()

if __name__ == "__main__":
    run_sql_script() 