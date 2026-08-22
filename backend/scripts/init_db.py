"""Creates the supervisors, runs, and activity_log tables. Run once:
    cd backend && python -m scripts.init_db"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.db import Base, engine


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables created (or already existed).")


if __name__ == "__main__":
    main()
