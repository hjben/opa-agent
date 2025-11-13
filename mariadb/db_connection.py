
from contextlib import contextmanager
from mysql.connector import pooling
from mariadb.db_config import MARIADB_CONFIG
 
import time

for i in range(10):
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="mcp_pool",
            pool_size=5,
            **MARIADB_CONFIG
        )
        break
    except Exception as e:
        print(f"Connection failed, retrying... ({i})")
        time.sleep(3)


@contextmanager
def db_cursor(dictionary=False):
    for i in range(10):
        try:
            conn = connection_pool.get_connection()
            break
        except Exception as e:
            print(f"Connection failed, retrying... ({i})")
            time.sleep(3)

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
