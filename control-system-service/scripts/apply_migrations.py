import os
from pathlib import Path

import psycopg2


def main() -> None:
    dsn = os.getenv("CONTROL_SYSTEM_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("CONTROL_SYSTEM_POSTGRES_DSN is required")
    migrations = sorted(
        (Path(__file__).parents[1] / "migrations").glob("*.sql")
    )
    if not migrations:
        raise RuntimeError("No Control System migrations were found")
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration.read_text(encoding="utf-8"))
                print(f"applied={migration.name}")


if __name__ == "__main__":
    main()
