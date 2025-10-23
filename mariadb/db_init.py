import os
import mysql.connector
from mysql.connector import errorcode
from db_config import MARIADB_CONFIG

def init_database():
    conn = None
    cursor = None
    try:
        # 데이터베이스 연결 (아직 DB가 없을 수도 있으므로 database 지정 X)
        conn = mysql.connector.connect(
            host=MARIADB_CONFIG["host"],
            port=MARIADB_CONFIG["port"],
            user=MARIADB_CONFIG["user"],
            password=MARIADB_CONFIG["password"]
        )
        cursor = conn.cursor()

        sql_file_path = os.path.join(os.path.dirname(__file__), "init.sql")
        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql_commands = f.read()

        # 여러 SQL 구문을 개별 실행
        for cmd in sql_commands.split(";"):
            cmd = cmd.strip()
            if cmd:
                try:
                    cursor.execute(cmd)
                except mysql.connector.Error as e:
                    # 이미 존재하는 DB/테이블 무시
                    if e.errno not in (errorcode.ER_DB_CREATE_EXISTS, errorcode.ER_TABLE_EXISTS_ERROR):
                        print(f"[SQL ERROR] {e}")
        
        conn.commit()
        print("✅ Database initialized successfully")

    except mysql.connector.Error as e:
        print(f"[DB INIT ERROR] {e}")

    finally:
        if cursor: cursor.close()
        if conn: conn.close()


if __name__ == "__main__":
    init_database()
