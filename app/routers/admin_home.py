from fastapi import Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AdminDep
from app.dependencies.csrf import CsrfTokenDep
from app.services import rooms as room_service
from app.utilities.flash import flash

from . import router, templates


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(
    request: Request,
    user: AdminDep,
):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "rooms": room_service.list_rooms()
        }
    )


@router.post("/admin/rooms/{room_id}/update")
async def update_room_action(
    request: Request,
    user: AdminDep,
    csrf: CsrfTokenDep,
    room_id: int,
    name: str = Form(),
    capacity: str = Form(),
):

    # Validate the capacity submitted through the form.
    try:
        room_capacity = int(capacity)
    except ValueError:
        flash(request, "Capacity must be a positive integer.", "danger")
        return RedirectResponse(
            url=request.url_for("admin_home_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Update the room using the existing room management service.
    result = room_service.update_room(
        room_id,
        {
            "name": name,
            "capacity": room_capacity,
        },
    )

    if result["ok"]:
        flash(request, "Room configuration updated successfully.")
    else:
        flash(request, result["error"], "danger")

    return RedirectResponse(
        url=request.url_for("admin_home_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/rooms/{room_id}/reset-capacity")
async def reset_room_capacity_action(
    request: Request,
    user: AdminDep,
    csrf: CsrfTokenDep,
    room_id: int,
):

    # Restore the system-defined default room capacity.
    result = room_service.update_room(
        room_id,
        {"capacity": None},
    )

    if result["ok"]:
        flash(request, "Room capacity restored to the default of 30.")
    else:
        flash(request, result["error"], "danger")

    return RedirectResponse(
        url=request.url_for("admin_home_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )