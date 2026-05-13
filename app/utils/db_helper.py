import pyodbc
from contextlib import contextmanager

DB_CONNECTION_STRING = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;'

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = pyodbc.connect(DB_CONNECTION_STRING)
        yield conn
    finally:
        if conn:
            conn.close()