from mariadb.db_connection import db_cursor

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