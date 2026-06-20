import base64, os, secrets
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import accounts, stats
from dotenv import load_dotenv

load_dotenv()

_WEB_USER = os.getenv("WEB_USER", "admin")
_WEB_PASS = os.getenv("WEB_PASSWORD", "")


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                user, _, password = base64.b64decode(auth[6:]).decode().partition(":")
                user_ok = secrets.compare_digest(user, _WEB_USER)
                pass_ok = secrets.compare_digest(password, _WEB_PASS)
                if user_ok and pass_ok:
                    return await call_next(request)
            except Exception:
                pass
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="RADIUS Analyzer"'},
            content="401 Unauthorized",
        )


app = FastAPI(title="RADIUS 帳號管理")
app.add_middleware(BasicAuthMiddleware)

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
