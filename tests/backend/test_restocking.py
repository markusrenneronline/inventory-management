"""
Tests for restocking order API endpoints.
"""
from datetime import datetime, timedelta


def _forecasts(client):
    return {f["item_sku"]: f for f in client.get("/api/demand").json()}


class TestRestockingEndpoints:
    """Test suite for restocking order endpoints."""

    def test_demand_forecasts_include_cost_and_lead_time(self, client):
        """Forecasts must carry the fields the restocking tab needs."""
        for forecast in client.get("/api/demand").json():
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["lead_time_days"] > 0

    def test_create_restocking_order(self, client):
        """Total and lead time are computed server-side; lead time is the longest item."""
        forecasts = _forecasts(client)
        skus = list(forecasts)[:2]
        payload = {"items": [{"sku": skus[0], "quantity": 10}, {"sku": skus[1], "quantity": 5}]}

        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")

        expected_total = 10 * forecasts[skus[0]]["unit_cost"] + 5 * forecasts[skus[1]]["unit_cost"]
        assert abs(order["total_value"] - expected_total) < 0.01

        expected_lead = max(forecasts[s]["lead_time_days"] for s in skus)
        assert order["lead_time_days"] == expected_lead

        delta = datetime.fromisoformat(order["expected_delivery"]) - datetime.fromisoformat(order["order_date"])
        assert delta == timedelta(days=expected_lead)

    def test_get_restocking_orders_lists_submitted_order(self, client):
        """A submitted order shows up first in the list (newest first)."""
        sku = next(iter(_forecasts(client)))
        created = client.post("/api/restocking-orders", json={"items": [{"sku": sku, "quantity": 1}]}).json()

        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json()[0]["id"] == created["id"]

    def test_create_order_rejects_unknown_sku(self, client):
        response = client.post("/api/restocking-orders", json={"items": [{"sku": "NOPE-000", "quantity": 1}]})
        assert response.status_code == 400
        assert "unknown sku" in response.json()["detail"].lower()

    def test_create_order_rejects_duplicate_sku(self, client):
        sku = next(iter(_forecasts(client)))
        items = [{"sku": sku, "quantity": 1}, {"sku": sku, "quantity": 2}]
        response = client.post("/api/restocking-orders", json={"items": items})
        assert response.status_code == 400

    def test_create_order_rejects_empty_items(self, client):
        response = client.post("/api/restocking-orders", json={"items": []})
        assert response.status_code == 422

    def test_create_order_rejects_non_positive_quantity(self, client):
        sku = next(iter(_forecasts(client)))
        for quantity in (0, -5):
            response = client.post("/api/restocking-orders", json={"items": [{"sku": sku, "quantity": quantity}]})
            assert response.status_code == 422

    def test_client_cannot_set_price(self, client):
        """Extra price fields in the request are ignored; server data wins."""
        forecasts = _forecasts(client)
        sku = next(iter(forecasts))
        payload = {"items": [{"sku": sku, "quantity": 2, "unit_cost": 0.01}]}
        order = client.post("/api/restocking-orders", json=payload).json()
        assert abs(order["total_value"] - 2 * forecasts[sku]["unit_cost"]) < 0.01
