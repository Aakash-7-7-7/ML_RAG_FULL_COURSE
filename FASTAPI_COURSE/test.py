from fastapi import FastAPI
from pydantic import BaseModel , Field

app=FastAPI()


class PostCreate(BaseModel):

    title:str=Field(min_length=2 , max_length=100)
    author:str=Field(min_length=2 , max_length=500)
    rating:float=Field(ge=0 , le=10)

class PostUpdate(BaseModel):
    title:str=Field(min_length=2 , max_length=100)
    author:str=Field(min_length=2 , max_length=500)
    rating:float=Field(ge=0 , le=10)

class PostResponse(BaseModel):
    title:str
    author:str
    rating:float

posts={
    1:{"title":"Atomic Habit" , "author":"James.D" , "rating":9.5},
    2:{"title":"Eat that Frog" , "author":"Kyle.J", "rating": 9.0}
}


@app.post("/post/{post_id}" , response_model=PostResponse)
def create_post(post_id: int , post:PostCreate):
    posts[post_id]={
        "title":post.title,
        "author":post.author,
        "rating":post.rating
    }
    return{
        "post_id":post_id,
        "title":post.title,
        "author":post.author,
        "rating":post.rating
    }


@app.get("/post", response_model=list[PostResponse])
def get_all():
    result=[]

    for post_id , post in posts.items():
        result.append({
            "post_id":post_id,
            "title":post['title'],
             "author":post["author"],
             "rating":post["rating"]
             })
    return result