import mysql.connector

def get_user_data(config, emp_id):
    conn = mysql.connector.connect(
        host="mariadb",
        user="root",
        password="rootpassword",
        database="user_db"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT emp_id, name, dept, role FROM users WHERE emp_id=%s", (emp_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result
