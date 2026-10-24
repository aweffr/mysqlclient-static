"""Read a parameterized query using an independent connection."""
import os

import MySQLdb
from MySQLdb.cursors import DictCursor


def connect():
    options = dict(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
    )
    if os.environ.get("DB_SSL_CA"):
        options.update(ssl={"ca": os.environ["DB_SSL_CA"]}, ssl_mode="VERIFY_IDENTITY")
    return MySQLdb.connect(**options)


def main():
    with connect() as connection:
        with connection.cursor(DictCursor) as cursor:
            cursor.execute("SELECT %s AS message, VERSION() AS server_version", ("你好，MySQL",))
            print(cursor.fetchone())


if __name__ == "__main__":
    main()
