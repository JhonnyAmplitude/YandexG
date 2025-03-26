from fastapi import FastAPI
from Users.router import router as user_router
from Campanies.router import router as campanos_router

app = FastAPI()

app.include_router(user_router, tags=["users"])
app.include_router(campanos_router, tags=["campanos"])
