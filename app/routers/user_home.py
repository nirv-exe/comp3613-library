from fastapi import Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep
from app.utilities.roles import dashboard_route_name

from . import router, templates


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(
    request: Request,
    user: AuthDep,
):
    if user.role in {"lecturer", "coordinator", "admin"}:
        return RedirectResponse(
            url=request.url_for(dashboard_route_name(user.role)),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={
            "user": user
        }
    )