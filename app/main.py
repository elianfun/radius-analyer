import os, secrets, time
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import accounts, stats
from dotenv import load_dotenv

load_dotenv()

_SECRET_KEY      = os.getenv("SECRET_KEY", secrets.token_hex(32))
_SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "1800"))
_WEB_USER        = os.getenv("WEB_USER", "admin")
_WEB_PASS        = os.getenv("WEB_PASSWORD", "")

_PUBLIC = {"/login"}


class SessionAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC or request.url.path.startswith("/static"):
            return await call_next(request)

        user          = request.session.get("user")
        last_activity = request.session.get("last_activity", 0)

        if not user or (time.time() - last_activity) > _SESSION_TIMEOUT:
            request.session.clear()
            return RedirectResponse(url="/login", status_code=302)

        request.session["last_activity"] = time.time()
        return await call_next(request)


app = FastAPI(title="RADIUS 帳號管理")
app.add_middleware(SessionAuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY, max_age=_SESSION_TIMEOUT)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(accounts.router)
app.include_router(stats.router)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user_ok = secrets.compare_digest(username, _WEB_USER)
    pass_ok = secrets.compare_digest(password, _WEB_PASS)
    if user_ok and pass_ok:
        request.session["user"]          = username
        request.session["last_activity"] = time.time()
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "帳號或密碼錯誤"}, status_code=401
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/accounts", response_class=HTMLResponse)
def accounts_page(request: Request):
    return templates.TemplateResponse("accounts.html", {"request": request})


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", {"request": request})
