"""Base class that every SQLAlchemy model in the project inherits from."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
