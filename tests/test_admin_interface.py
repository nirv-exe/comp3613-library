import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.dependencies.auth import get_current_user
from app.main import app
from app.models.room import Room
from app.services import rooms


@pytest.fixture
def admin_client(test_engine, monkeypatch):

    monkeypatch.setattr(rooms, "default_engine", test_engine)

    with Session(test_engine) as session:
        session.add(Room(id=1, name="Workshop A", capacity=None))
        session.add(Room(id=2, name="Workshop B", capacity=45))
        session.commit()

    current_user = SimpleNamespace(
        id=1,
        username="admin",
        role="admin",
    )

    async def mock_current_user():
        if current_user.role is None:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
            )
        return current_user

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = mock_current_user

    client = TestClient(app)

    try:
        yield client, current_user
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def get_csrf_token(client):

    response = client.get("/admin")

    assert response.status_code == 200

    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        response.text,
    )

    assert match is not None

    return match.group(1)


def submit_room_update(client, room_id, name, capacity):

    token = get_csrf_token(client)

    return client.post(
        f"/admin/rooms/{room_id}/update",
        data={
            "name": name,
            "capacity": capacity,
            "csrf_token": token,
        },
        follow_redirects=True,
    )


def test_admin_dashboard_access(admin_client):

    client, user = admin_client

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Administrator dashboard" in response.text


def test_admin_dashboard_displays_all_rooms(admin_client):

    client, user = admin_client

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Workshop A" in response.text
    assert "Workshop B" in response.text


def test_admin_dashboard_displays_effective_capacities(admin_client):

    client, user = admin_client

    response = client.get("/admin")

    assert response.status_code == 200
    assert "30 students" in response.text
    assert "45 students" in response.text
    assert "Default capacity" in response.text
    assert "Custom capacity" in response.text


def test_admin_can_update_room_name(admin_client):

    client, user = admin_client

    response = submit_room_update(
        client, 1, "Training Room A", "30"
    )

    assert response.status_code == 200
    assert "Room configuration updated successfully." in response.text
    assert rooms.get_room(1)["name"] == "Training Room A"


def test_admin_can_update_room_capacity(admin_client):

    client, user = admin_client

    response = submit_room_update(
        client, 1, "Workshop A", "50"
    )

    assert response.status_code == 200
    assert "Room configuration updated successfully." in response.text
    assert rooms.get_room(1)["capacity"] == 50
    assert rooms.get_room(1)["effective_capacity"] == 50


def test_admin_can_restore_default_capacity(admin_client):

    client, user = admin_client

    token = get_csrf_token(client)

    response = client.post(
        "/admin/rooms/2/reset-capacity",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Room capacity restored to the default of 30." in response.text
    assert rooms.get_room(2)["capacity"] is None
    assert rooms.get_room(2)["effective_capacity"] == 30
    assert rooms.get_room(2)["name"] == "Workshop B"


def test_admin_cannot_use_duplicate_room_name(admin_client):

    client, user = admin_client

    response = submit_room_update(
        client, 1, "Workshop B", "50"
    )

    assert response.status_code == 200
    assert "room name already exists" in response.text
    assert rooms.get_room(1)["name"] == "Workshop A"
    assert rooms.get_room(1)["capacity"] is None


def test_admin_cannot_use_whitespace_room_name(admin_client):

    client, user = admin_client

    response = submit_room_update(
        client, 1, "   ", "50"
    )

    assert response.status_code == 200
    assert "name must be a non-empty string" in response.text
    assert rooms.get_room(1)["name"] == "Workshop A"
    assert rooms.get_room(1)["capacity"] is None


@pytest.mark.parametrize("capacity", ["0", "-10", "25.5", "abc"])
def test_admin_cannot_use_invalid_capacity(admin_client, capacity):

    client, user = admin_client

    response = submit_room_update(
        client, 1, "Workshop A", capacity
    )

    assert response.status_code == 200
    assert "positive integer" in response.text
    assert rooms.get_room(1)["capacity"] is None


def test_admin_cannot_update_nonexistent_room(admin_client):

    client, user = admin_client

    response = submit_room_update(
        client, 999, "Unknown Room", "40"
    )

    assert response.status_code == 200
    assert "room not found" in response.text
    assert rooms.get_room(999) is None


def test_admin_cannot_reset_nonexistent_room(admin_client):

    client, user = admin_client

    token = get_csrf_token(client)

    response = client.post(
        "/admin/rooms/999/reset-capacity",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "room not found" in response.text


@pytest.mark.parametrize("role", [None, "lecturer", "coordinator"])
def test_non_admin_cannot_access_dashboard(admin_client, role):

    client, user = admin_client

    user.role = role

    response = client.get(
        "/admin",
        follow_redirects=False,
    )

    assert response.status_code == 401


@pytest.mark.parametrize("role", [None, "lecturer", "coordinator"])
def test_non_admin_cannot_update_room(admin_client, role):

    client, user = admin_client

    token = get_csrf_token(client)

    user.role = role

    response = client.post(
        "/admin/rooms/1/update",
        data={
            "name": "Unauthorized Room",
            "capacity": "100",
            "csrf_token": token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert rooms.get_room(1)["name"] == "Workshop A"
    assert rooms.get_room(1)["capacity"] is None


@pytest.mark.parametrize("role", [None, "lecturer", "coordinator"])
def test_non_admin_cannot_reset_capacity(admin_client, role):

    client, user = admin_client

    token = get_csrf_token(client)

    user.role = role

    response = client.post(
        "/admin/rooms/2/reset-capacity",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert rooms.get_room(2)["capacity"] == 45


@pytest.mark.parametrize("token_type", ["missing", "invalid"])
def test_room_update_requires_valid_csrf(admin_client, token_type):

    client, user = admin_client

    get_csrf_token(client)

    data = {
        "name": "Unauthorized Change",
        "capacity": "100",
    }

    if token_type == "invalid":
        data["csrf_token"] = "invalid-token"

    response = client.post(
        "/admin/rooms/1/update",
        data=data,
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert rooms.get_room(1)["name"] == "Workshop A"
    assert rooms.get_room(1)["capacity"] is None


@pytest.mark.parametrize("token_type", ["missing", "invalid"])
def test_capacity_reset_requires_valid_csrf(admin_client, token_type):

    client, user = admin_client

    get_csrf_token(client)

    data = {}

    if token_type == "invalid":
        data["csrf_token"] = "invalid-token"

    response = client.post(
        "/admin/rooms/2/reset-capacity",
        data=data,
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert rooms.get_room(2)["capacity"] == 45


def test_admin_can_access_coordinator_dashboard(admin_client):

    client, user = admin_client

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Coordinator dashboard" in response.text
    assert 'href="http://testserver/coordinator"' in response.text

    response = client.get("/coordinator")

    assert response.status_code == 200
    assert "Coordinator dashboard" in response.text