
from contextlib import contextmanager
from mysql.connector import pooling
from config.db_config import MARIADB_CONFIG
 
import time

connection_pool = None

# 최대 10회 시도
for i in range(10):
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="mcp_pool",
            pool_size=10,
            **MARIADB_CONFIG
        )
        print("Connection pool created")
        break
    except Exception as e:
        print(f"Connection pool creation failed, retrying... ({i+1}/10)")
        time.sleep(3)

if connection_pool is None:
    raise RuntimeError("Failed to create connection pool after multiple attempts")


@contextmanager
def db_cursor(dictionary=False):
    conn = connection_pool.get_connection()
    try:
        with conn.cursor(dictionary=dictionary) as cursor:
            yield cursor
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
