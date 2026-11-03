"""
Tests for task API endpoints.
"""
import pytest

from mock_data import tasks as task_store


@pytest.fixture(autouse=True)
def clean_tasks():
    """Tasks live in a module-level list; reset it so tests stay independent."""
    task_store.clear()
    yield
    task_store.clear()


def _create(client, **overrides):
    payload = {"title": "Check stock", "priority": "high", "dueDate": "2025-10-08", **overrides}
    return client.post("/api/tasks", json=payload)


class TestTaskEndpoints:
    """Test suite for task-related endpoints."""

    def test_get_tasks_empty(self, client):
        """Test getting tasks when none exist."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task returns 201 and a string ID."""
        response = _create(client)
        assert response.status_code == 201

        task = response.json()
        assert task["title"] == "Check stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2025-10-08"
        assert task["status"] == "pending"
        # String ID so it cannot collide with numeric client-side mock task IDs
        assert isinstance(task["id"], str)
        assert task["id"].startswith("task-")

    def test_get_tasks_newest_first(self, client):
        """Test that the newest task is returned first."""
        _create(client, title="first")
        _create(client, title="second")

        titles = [t["title"] for t in client.get("/api/tasks").json()]
        assert titles == ["second", "first"]

    def test_task_ids_not_reused_after_delete(self, client):
        """Test that deleting a task does not cause its ID to be reused."""
        first = _create(client).json()
        client.delete(f"/api/tasks/{first['id']}")
        second = _create(client).json()
        assert second["id"] != first["id"]

    def test_create_task_empty_title(self, client):
        """Test that an empty title is rejected."""
        assert _create(client, title="").status_code == 422

    def test_create_task_invalid_priority(self, client):
        """Test that an unknown priority is rejected."""
        assert _create(client, priority="urgent").status_code == 422

    def test_toggle_task(self, client):
        """Test toggling a task between pending and completed."""
        task_id = _create(client).json()["id"]

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.json()["status"] == "pending"

    def test_delete_task(self, client):
        """Test deleting a task."""
        task_id = _create(client).json()["id"]

        assert client.delete(f"/api/tasks/{task_id}").status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_toggle_nonexistent_task(self, client):
        """Test toggling a task that doesn't exist."""
        response = client.patch("/api/tasks/task-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist."""
        response = client.delete("/api/tasks/task-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
