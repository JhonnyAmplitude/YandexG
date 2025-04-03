from fastapi import FastAPI
from Users.router import router as user_router
from Campanies.router import router as campanos_router
from ReportsDirect.router import router as report_router
from ReportsMetrica.router import router as metrics_router
app = FastAPI()

app.include_router(user_router, tags=["users"])
app.include_router(campanos_router, tags=["campanies"])
app.include_router(report_router, tags=["direct_reports"])

app.include_router(metrics_router, tags=["metrica_reports"])



