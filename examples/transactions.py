"""Explicit commit and rollback; uses a connection-local temporary table."""
from basic import connect


def main():
    with connect() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TEMPORARY TABLE example_message (message VARCHAR(255))")
                cursor.execute("INSERT INTO example_message (message) VALUES (%s)", ("事务示例",))
                cursor.execute("SELECT message FROM example_message")
                print(cursor.fetchall())
            connection.commit()
        except Exception:
            connection.rollback()
            raise


if __name__ == "__main__":
    main()
