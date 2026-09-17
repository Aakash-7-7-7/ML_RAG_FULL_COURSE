from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# 1. Database Connection URL (PostgreSQL)
# In production, pull this from environment variables via os.getenv()
DATABASE_URL = "postgresql://user:password@localhost:5432/movies_db"

# 2. Engine & Session Setup
# Connection pooling is handled automatically by SQLAlchemy for PostgreSQL
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 3. SQLAlchemy Database Model
class PostDB(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    movie_name = Column(String(255), nullable=False)
    rating = Column(Float, nullable=False)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# 4. Pydantic Schemas (Data Validation)
class PostCreate(BaseModel):
    movie_name: str
    rating: float

class PostResponse(BaseModel):
    id: int
    movie_name: str
    rating: float

    model_config = ConfigDict(from_attributes=True)

app = FastAPI()

# 5. Dependency Injection for DB Session Management
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoint Handlers ---

@app.post("/posts", status_code=status.HTTP_201_CREATED)
def insert_in_table(payload: PostCreate, db: Session = Depends(get_db)):
    new_post = PostDB(movie_name=payload.movie_name, rating=payload.rating)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return {"message": "Post Created", "post_id": new_post.id}

@app.put("/posts/update/{post_id}")
def update(post_id: int, payload: PostCreate, db: Session = Depends(get_db)):
    post = db.query(PostDB).filter(PostDB.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.movie_name = payload.movie_name
    post.rating = payload.rating
    db.commit()
    return {"message": "Post Updated", "post_id": post.id}

@app.delete("/posts/{post_id}")
def delete(post_id: int, db: Session = Depends(get_db)):
    post = db.query(PostDB).filter(PostDB.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    db.delete(post)
    db.commit()
    return {"message": "Post deleted", "post_id": post_id}

@app.get("/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(PostDB).filter(PostDB.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.get("/posts", response_model=List[PostResponse])
def get_all_posts(db: Session = Depends(get_db)):
    posts = db.query(PostDB).all()
    return posts