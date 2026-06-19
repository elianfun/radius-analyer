from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.routes import accounts, stats

app = FastAPI(title="RADIUS 帳號管理")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(accounts.router)
app.include_router(stats.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request):
    return templates.TemplateResponse("accounts.html", {"request": request})


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", {"request": request})
