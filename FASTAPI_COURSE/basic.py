from fastapi import FastAPI , status
from pydantic import BaseModel , Field

app=FastAPI()

class PostCreate(BaseModel):
    movie_name:str=Field(min_length=2 , max_length=100)
    rating:float=Field(ge=0 , le=10)

class PostUpdate(BaseModel):
    movie_name:str=Field(min_length=2 , max_length=100)
    rating: float=Field(ge=0 , le=10)

class PostResponse(BaseModel):
    post_id:int
    movie_name:str
    rating:float



posts={
    1:{"movie_name":"Fight Club" , "rating":9.5},
    2:{"movie_name":"Ineterstellar" , "rating": 9.0}
}

#! Create 

@app.post("/post/{post_id}" , response_model=PostResponse)
def create_post(post_id:int , post:PostCreate):
    posts[post_id]={
        "movie_name":post.movie_name,
        "rating":post.rating
    }

    return{
        "post_id":post_id,
        "movie_name":post.movie_name,
        "rating":post.rating
    }



#! READ ONE

@app.get("/post/{post_id}" , response_model=PostResponse)
def get_posts(post_id:int):
    post=posts[post_id]

    return{
        "post_id":post_id,
        "movie_name": post["movie_name"],
        "rating": post["rating"]
    }


#! UPDATE

@app.put(
    "/posts/{post_id}",
    response_model=PostResponse
)
def update_post(post_id: int, post: PostUpdate):

    posts[post_id] = {
        "movie_name": post.movie_name,
        "rating": post.rating
    }

    return {
        "post_id": post_id,
        "movie_name": post.movie_name,
        "rating": post.rating
    }


#! DELETE 

@app.delete("/posts/{post_id}")
def delete_post(post_id: int):

    del posts[post_id]



#! READ ALL 

@app.get("/post" , response_model=list[PostResponse])
def get_all_posts():
    result=[]

    for post_id , post in posts.items():
        result.append({
            "post_id":post_id,
            "movie_name":post['movie_name'],
            "rating":post["rating"]
        })

    return result