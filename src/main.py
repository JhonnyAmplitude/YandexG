from fastapi import FastAPI
from src.Users.router import router as user_router
from src.Campanies.router import router as campanos_router
from src.ReportsDirect.router import router as report_router
from src.ReportsMetrica.router import router as metrics_router
from src.Metrica_goals.router import router as goals_router

app = FastAPI()

app.include_router(user_router, tags=["users"])
app.include_router(campanos_router, tags=["campanies"])
app.include_router(report_router, tags=["direct_reports"])
app.include_router(metrics_router, tags=["metrica_reports"])
app.include_router(goals_router)



