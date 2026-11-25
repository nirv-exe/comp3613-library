"""Role-to-dashboard routing shared by the landing page and sign-in flow."""


def dashboard_route_name(role: str) -> str:
    return {
        "lecturer": "lecturer_home_view",
        "coordinator": "coordinator_home_view",
        "admin": "admin_home_view",
    }.get(role, "user_home_view")
