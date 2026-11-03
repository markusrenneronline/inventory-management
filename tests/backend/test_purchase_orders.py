"""
Tests for purchase order API endpoints.
"""
import pytest

from mock_data import purchase_orders as po_store


@pytest.fixture(autouse=True)
def clean_purchase_orders():
    """Purchase orders live in a module-level list; restore it after each test."""
    original = list(po_store)
    yield
    po_store[:] = original


def _backlog_id(client):
    return client.get("/api/backlog").json()[0]["id"]


def _payload(backlog_item_id, **overrides):
    return {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply",
        "quantity": 50,
        "unit_cost": 12.5,
        "expected_delivery_date": "2025-11-15",
        "notes": "Rush",
        **overrides,
    }


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_purchase_order(self, client):
        """Test creating a purchase order for a backlog item."""
        backlog_id = _backlog_id(client)
        response = client.post("/api/purchase-orders", json=_payload(backlog_id))
        assert response.status_code == 201

        po = response.json()
        assert po["backlog_item_id"] == backlog_id
        assert po["supplier_name"] == "Acme Supply"
        assert po["quantity"] == 50
        assert po["unit_cost"] == 12.5
        assert po["status"] == "ordered"
        assert po["id"]
        assert po["created_date"]

    def test_create_sets_has_purchase_order_on_backlog(self, client):
        """Test that the backlog flag reflects the new purchase order."""
        backlog_id = _backlog_id(client)
        client.post("/api/purchase-orders", json=_payload(backlog_id))

        item = next(b for b in client.get("/api/backlog").json() if b["id"] == backlog_id)
        assert item["has_purchase_order"] is True

    def test_get_purchase_order_by_backlog_item(self, client):
        """Test fetching a purchase order by its backlog item."""
        backlog_id = _backlog_id(client)
        created = client.post("/api/purchase-orders", json=_payload(backlog_id)).json()

        response = client.get(f"/api/purchase-orders/{backlog_id}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_purchase_order_without_po(self, client):
        """Test fetching a purchase order for a backlog item that has none."""
        response = client.get(f"/api/purchase-orders/{_backlog_id(client)}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_for_nonexistent_backlog_item(self, client):
        """Test creating a purchase order for an unknown backlog item."""
        response = client.post("/api/purchase-orders", json=_payload("nonexistent-999"))
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_duplicate_purchase_order(self, client):
        """Test that a second purchase order for the same backlog item is rejected."""
        backlog_id = _backlog_id(client)
        assert client.post("/api/purchase-orders", json=_payload(backlog_id)).status_code == 201
        assert client.post("/api/purchase-orders", json=_payload(backlog_id)).status_code == 409

    @pytest.mark.parametrize("overrides", [{"quantity": 0}, {"quantity": -5}, {"unit_cost": -1}])
    def test_create_with_invalid_numbers(self, client, overrides):
        """Test that non-positive quantity and negative cost are rejected."""
        response = client.post("/api/purchase-orders", json=_payload(_backlog_id(client), **overrides))
        assert response.status_code == 400

    def test_create_missing_required_field(self, client):
        """Test that a missing supplier is rejected by validation."""
        payload = _payload(_backlog_id(client))
        del payload["supplier_name"]
        assert client.post("/api/purchase-orders", json=payload).status_code == 422
