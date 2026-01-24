
import pytest
from fastapi.testclient import TestClient
from api.main import app

class TestAPI:
    def setup_method(self):
        self.client = TestClient(app)

    def test_optimize_endpoint_exists(self):
        """Test that the /optimize endpoint is available and accepts POST."""
        # We don't want to start a real long-running task, so we just check for validation error
        # or mock the manager later if needed. For now, check validation.
        response = self.client.post("/optimize", json={})
        assert response.status_code == 422 # Validation Error (missing fields)

    def test_get_task_not_found(self):
        """Test status retrieval for non-existent task."""
        response = self.client.get("/tasks/non-existent-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_optimize_success_mocked(self):
        """Test successful task submission with valid data."""
        request_data = {
            "target_code": "def test(): pass",
            "test_code": "def check(): pass",
            "config": {"generations": 1}
        }
        # This will actually call start_task which is async and uses the task manager.
        # It should return a TaskStatus object.
        response = self.client.post("/optimize", json=request_data)
        assert response.status_code == 200
        assert "task_id" in response.json()
        assert response.json()["status"] in ["queued", "running", "completed"]
