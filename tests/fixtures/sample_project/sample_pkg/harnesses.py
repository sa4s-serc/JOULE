def membership_harness(target) -> None:
    values = list(range(50)) * 50
    for _ in range(10):
        result = target(values)
        assert result > 0


def concat_report_harness(target) -> None:
    words = ["alpha", "beta", "", "gamma"]
    output = target(words, 4)
    assert output.count("|") == 12


def warehouse_pipeline_harness(target) -> None:
    orders = [
        {
            "order_id": "o1",
            "source": "N",
            "destination": "E",
            "sku": "bolt",
            "quantity": 4,
            "priority": "high",
            "preferred_hub": "NORTH",
        },
        {
            "order_id": "o2",
            "source": "N",
            "destination": "W",
            "sku": "nut",
            "quantity": 8,
            "priority": "normal",
            "preferred_hub": "NORTH",
        },
        {
            "order_id": "o3",
            "source": "S",
            "destination": "E",
            "sku": "bolt",
            "quantity": 3,
            "priority": "critical",
            "preferred_hub": "SOUTH",
        },
    ]
    hub_capacities = {"NORTH": 10, "SOUTH": 5}
    route_costs = {("N", "E"): 2, ("N", "W"): 4, ("S", "E"): 3}

    payload = target(orders, hub_capacities, route_costs)
    assert payload["total_orders"] == 3
    assert "hub_loads" in payload
