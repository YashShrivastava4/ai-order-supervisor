"""One-time setup: creates the supervisors, runs, and activity_log tables.

Run this once after Postgres is up and before starting the worker/API:
    cd backend
    python -m scripts.init_db
"""

from app.db import Base, engine


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables created (or already existed).")


if __name__ == "__main__":
    main()
