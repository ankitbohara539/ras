from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.router import api_router
from app.core.config import get_settings
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.data import SessionLocal
from app.model import Task as TaskModel

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


class TaskCreate(BaseModel):
    title: str
    description: str
    isCompleted: bool = False


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "API is working correctly"}


@app.get("/tasks")
def get_tasks(db: Session = Depends(get_db)):
    return db.query(TaskModel).all()


@app.post("/tasks")
def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    new_task = TaskModel(
        title=task.title,
        description=task.description,
        isCompleted = task.isCompleted
        
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return {
        "message": "Task created",
        "task": new_task
    }

@app.get("/healthdb")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "connected"}