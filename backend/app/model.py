from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

from app.data import engine

Base = declarative_base()

class Task(Base):
    __tablename__ = "basic_crud"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    isCompleted = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)