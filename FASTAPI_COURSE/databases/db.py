from sqlalchemy import create_engine , Integer , text
from sqlalchemy.orm import Session , DeclarativeBase , Mapped , mapped_column


class Base(DeclarativeBase):
    pass

class Post(Base):
    __tablename__="posts"
    id:Mapped[int]=mapped_column(primary_key=True)
    movie_name:Mapped[str]=mapped_column(nullable=False)
    rating:Mapped[float]=mapped_column(nullable=False)

engine=create_engine("sqlite:///database.db", echo=False)
Base.metadata.create_all(engine)