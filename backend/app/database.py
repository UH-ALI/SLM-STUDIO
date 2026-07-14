from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings  # Pydantic settings — reads validated values from .env

# Create the SQLAlchemy engine — the single persistent connection pool to PostgreSQL.
# settings.DATABASE_URL is already validated by Pydantic on startup,
# so if DATABASE_URL is missing from .env the app refuses to start immediately.
#
# pool_pre_ping=True → before using any connection from the pool, SQLAlchemy sends
#                      a lightweight "SELECT 1" to check it is still alive.
#                      This is critical in Docker where the DB container can restart
#                      independently and leave stale connections in the pool.
# pool_size=5        → keep 5 persistent connections open at all times
# max_overflow=10    → allow up to 10 extra connections under heavy load
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Session factory — each request gets its own isolated database session.
# autocommit=False → changes must be explicitly committed (safer default)
# autoflush=False  → SQLAlchemy won't auto-flush pending changes before queries
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class that all SQLAlchemy models (User, Dataset, TrainingJob etc.) inherit from.
# Calling Base.metadata.create_all(engine) on startup creates any missing tables.
Base = declarative_base()


# ---------------------------------------------------------
# DATABASE SESSION DEPENDENCY
# ---------------------------------------------------------
def get_db():
    """
    FastAPI dependency that provides a database session for the duration of a request.
    Used with Depends(get_db) in every router that needs database access.
    The session is always closed in the finally block — even if the request raises
    an exception — so connections are never leaked back into the pool.
    """
    db = SessionLocal()
    try:
        yield db       # inject the session into the route handler
    finally:
        db.close()     # return the connection to the pool when the request ends