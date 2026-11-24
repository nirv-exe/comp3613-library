import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import get_session
from app.main import app
from app.models.user import User
from app.routers import template_env
from app.utilities.security import create_access_token, encrypt_password

ROLE_ROUTES = {
    "lecturer": ("/lecturer", "lecturer_home_view"),
    "coordinator": ("/coordinator", "coordinator_home_view"),
    "admin": ("/admin", "admin_home_view"),
}


@pytest.fixture
def frontend_client(test_engine):
    def override_session():
        with Session(test_engine) as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = override_session

    encoded_password = encrypt_password("test-password")
    with Session(test_engine) as session:
        for user_id, role in enumerate(ROLE_ROUTES, start=1):
            session.add(
                User(
                    id=user_id,
                    username=role,
                    email=f"{role}@example.com",
                    password=encoded_password,
                    role=role,
                )
            )
        session.commit()

    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def _csrf_token(response) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


@pytest.mark.parametrize(("role", "path"), [(role, route[0]) for role, route in ROLE_ROUTES.items()])
def test_role_dashboard_and_legacy_route(frontend_client, role, path):
    frontend_client.cookies.set(
        "access_token",
        create_access_token({"sub": str(list(ROLE_ROUTES).index(role) + 1), "role": role}),
    )

    dashboard = frontend_client.get(path)
    legacy = frontend_client.get("/app", follow_redirects=False)

    assert dashboard.status_code == 200
    assert f"/{role}" in dashboard.text
    assert legacy.status_code == 303
    assert legacy.headers["location"].endswith(path)


def test_dashboard_role_guard_rejects_other_authenticated_roles(frontend_client):
    frontend_client.cookies.set(
        "access_token",
        create_access_token({"sub": "1", "role": "lecturer"}),
    )

    coordinator_response = frontend_client.get("/coordinator")
    admin_response = frontend_client.get("/admin")

    assert coordinator_response.status_code == 403
    assert admin_response.status_code == 401


def test_administrator_can_access_coordinator_dashboard(frontend_client):
    frontend_client.cookies.set(
        "access_token",
        create_access_token({"sub": "3", "role": "admin"}),
    )

    response = frontend_client.get("/coordinator")

    assert response.status_code == 200
    assert "Coordinator dashboard" in response.text
    assert re.search(r'href="[^"]*/admin"', response.text)
    assert re.search(r'href="[^"]*/coordinator"', response.text)


def test_jinja_autoescapes_html_xml_and_user_content(frontend_client, test_engine):
    with Session(test_engine) as session:
        lecturer = session.get(User, 1)
        assert lecturer is not None
        lecturer.username = "<img src=x onerror=alert(1)>"
        session.add(lecturer)
        session.commit()

    frontend_client.cookies.set(
        "access_token",
        create_access_token({"sub": "1", "role": "lecturer"}),
    )
    response = frontend_client.get("/lecturer")

    assert response.status_code == 200
    assert "&lt;img src=x onerror=alert(1)&gt;" in response.text
    assert "<img src=x onerror=alert(1)>" not in response.text
    assert template_env.autoescape("example.html")
    assert template_env.autoescape("example.xml")


@pytest.mark.parametrize(("role", "path"), [(role, route[0]) for role, route in ROLE_ROUTES.items()])
def test_html_login_redirects_to_role_dashboard(frontend_client, role, path):
    token = _csrf_token(frontend_client.get("/login"))

    response = frontend_client.post(
        "/login",
        data={"username": role, "password": "test-password", "csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(path)
    assert "httponly" in response.headers["set-cookie"].lower()


def test_html_form_csrf_rejects_missing_and_cross_session_tokens(frontend_client):
    token = _csrf_token(frontend_client.get("/register"))
    other_client = TestClient(app)
    other_token = _csrf_token(other_client.get("/register"))
    assert token != other_token

    missing = frontend_client.post(
        "/register",
        data={"username": "alice", "email": "alice@example.com", "password": "secret"},
    )
    cross_session = other_client.post(
        "/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "secret",
            "csrf_token": token,
        },
    )

    assert missing.status_code == 403
    assert cross_session.status_code == 403
    other_client.close()


def test_html_form_csrf_rejects_non_ascii_token(frontend_client):
    response = frontend_client.get("/register")
    token = _csrf_token(response)

    rejected = frontend_client.post(
        "/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "secret",
            "csrf_token": "é",
        },
    )

    assert token.isascii()
    assert rejected.status_code == 403


def test_html_form_accepts_session_csrf_token(frontend_client):
    token = _csrf_token(frontend_client.get("/register"))

    response = frontend_client.post(
        "/register",
        data={
            "username": "new-lecturer",
            "email": "new-lecturer@example.com",
            "password": "secret",
            "csrf_token": token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")
