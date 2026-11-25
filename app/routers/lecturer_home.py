from fastapi import Request
from fastapi.responses import HTMLResponse

from app.dependencies.auth import LecturerDep

from . import router, templates


@router.get("/lecturer", response_class=HTMLResponse, name="lecturer_home_view")
async def lecturer_home_view(request: Request, user: LecturerDep):
    return templates.TemplateResponse(
        request=request,
        name="lecturer.html",
        context={"user": user},
    )
