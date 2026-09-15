import os
import psycopg2
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def inspect_db():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment variables or .env file.")
        return

    try:
        print("Connecting to the database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("Successfully connected!\n")

        # Get list of tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()
        
        print("Found Tables:")
        for table in tables:
            table_name = table[0]
            print(f"- {table_name}")
            
            # Get columns for each table
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s
            """, (table_name,))
            columns = cursor.fetchall()
            for col in columns:
                print(f"    - {col[0]} ({col[1]})")
            print()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    inspect_db()
