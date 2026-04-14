import sqlite3
import os

# This finds the correct path to the database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'college0.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

def get_connection():
    """Returns a connection to the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # this lets us access columns by name instead of index
    return conn

def init_db():
    """Creates all the tables by running schema.sql"""
    conn = get_connection()
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()