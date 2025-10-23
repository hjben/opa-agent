import os

MARIADB_CONFIG = {
    "host": os.getenv("MARIADB_HOST", "mariadb"),
    "port": int(os.getenv("MARIADB_PORT", 3306)),
    "user": os.getenv("MARIADB_USER", "root"),
    "password": os.getenv("MARIADB_PASSWORD", "rootpassword"),
    "database": os.getenv("MARIADB_DB", "opa_db"),
}
