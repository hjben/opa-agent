from contextlib import contextmanager
from mysql.connector import pooling
import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "rootpassword"),
    "database": os.getenv("DB_NAME", "opa_db"),
}

# Connection Pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name="mcp_pool",
    pool_size=5,
    **DB_CONFIG
)

@contextmanager
def db_cursor(dictionary=False):
    """자동으로 연결 및 커서 닫기를 처리하는 헬퍼"""
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

# ===================================
# USER TABLE CRUD
# ===================================

def get_user_by_id(emp_id: str):
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM user WHERE emp_id=%s", (emp_id,))
        return cursor.fetchone()


def get_all_users():
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM user")
        return cursor.fetchall()


def add_user(emp_id, name, dept, role):
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO user (emp_id, name, dept, role) VALUES (%s, %s, %s, %s)",
            (emp_id, name, dept, role)
        )


def delete_user(emp_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM user WHERE emp_id=%s", (emp_id,))

# ===================================
# API TABLE CRUD
# ===================================

def get_api_by_id(api_id: int):
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM api WHERE api_id=%s", (api_id,))
        return cursor.fetchone()


def get_all_apis():
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM api")
        return cursor.fetchall()


def add_api(api_name, endpoint, method, description=None):
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO api (api_name, endpoint, method, description) VALUES (%s, %s, %s, %s)",
            (api_name, endpoint, method, description)
        )


def delete_api(api_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM api WHERE api_id=%s", (api_id,))

# ===================================
# POLICY TABLE CRUD
# ===================================

def get_policy_by_id(policy_id: int):
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM policy WHERE policy_id=%s", (policy_id,))
        return cursor.fetchone()


def get_all_policies():
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM policy")
        return cursor.fetchall()


def add_policy(policy_name, api_id, emp_id, rego_code, is_active=True):
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO policy (policy_name, api_id, emp_id, rego_code, is_active) VALUES (%s, %s, %s, %s, %s)",
            (policy_name, api_id, emp_id, rego_code, is_active)
        )


def delete_policy(policy_id):
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM policy WHERE policy_id=%s", (policy_id,))