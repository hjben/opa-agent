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
