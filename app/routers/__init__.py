from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.utilities.flash import get_flashed_messages
from app.utilities.security import get_csrf_token


template_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(("html", "htm", "xml")),
)
template_env.globals['get_flashed_messages'] = get_flashed_messages
template_env.globals["csrf_token"] = get_csrf_token
templates = Jinja2Templates(env=template_env)
static_files = StaticFiles(directory="app/static")

router = APIRouter(tags=["Jinja Based Endpoints"], include_in_schema=get_settings().env.lower() in ["dev","development"])
api_router = APIRouter(tags=["API Endpoints"], prefix="/api")

from . import (
    index,
    login,
    register,
    admin_home,
    user_home,
    lecturer_home,
    coordinator_home,
    users,
    logout,
    server_config,
    library,
)

api_router.include_router(library.router)