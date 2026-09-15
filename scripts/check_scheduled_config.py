from app.config import Settings


def check(settings):
    if not settings.database_url.startswith("postgresql+psycopg://"):
        raise ValueError("Scheduled jobs require persistent PostgreSQL DATABASE_URL")


if __name__ == "__main__":
    check(Settings())
