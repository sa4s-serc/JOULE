from sample_pkg.complex_cases import telemetry_triage_pipeline, warehouse_balancing_pipeline


def test_warehouse_balancing_pipeline() -> None:
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
        {
            "order_id": "o1",
            "source": "N",
            "destination": "E",
            "sku": "bolt",
            "quantity": 2,
            "priority": "high",
            "preferred_hub": "NORTH",
        },
        {
            "order_id": "",
            "source": "Q",
            "destination": "R",
            "sku": "washer",
            "quantity": 2,
            "priority": "low",
            "preferred_hub": "SOUTH",
        },
        {
            "order_id": "o4",
            "source": "X",
            "destination": "Y",
            "sku": "pin",
            "quantity": 2,
            "priority": "normal",
            "preferred_hub": "EAST",
        },
    ]

    hub_capacities = {"NORTH": 10, "SOUTH": 5}
    route_costs = {("N", "E"): 2, ("N", "W"): 4, ("S", "E"): 3, ("X", "Y"): 6}

    result = warehouse_balancing_pipeline(orders, hub_capacities, route_costs)

    assert result["total_orders"] == 4
    assert result["skipped_orders"] == ["o1", "missing-order-id"]
    assert result["unassigned_order_ids"] == ["o2"]
    assert result["hub_loads"] == {"NORTH": 6, "OVERFLOW": 8, "SOUTH": 3}
    assert result["top_routes"][0] == {"route": "N->W", "cost": 32}
    assert result["top_skus"][0] == {"sku": "nut", "quantity": 8}
    assert "hub=NORTH;" in result["operational_digest"]


def test_telemetry_triage_pipeline() -> None:
    events = [
        {
            "event_id": "e1",
            "service": "api",
            "region": "us-east",
            "latency_ms": 120,
            "error_count": 10,
            "throughput": 80,
            "tags": ["db", "slow"],
        },
        {
            "event_id": "e2",
            "service": "api",
            "region": "us-east",
            "latency_ms": 140,
            "error_count": 15,
            "throughput": 70,
            "tags": ["db"],
        },
        {
            "event_id": "e3",
            "service": "worker",
            "region": "eu-west",
            "latency_ms": 60,
            "error_count": 1,
            "throughput": 90,
            "tags": ["cache"],
        },
        {
            "event_id": "e4",
            "service": "api",
            "region": "us-east",
            "latency_ms": -2,
            "error_count": 0,
            "throughput": 50,
            "tags": ["invalid"],
        },
    ]

    thresholds = {
        "latency_ms": 100.0,
        "error_rate": 0.1,
        "throughput": 50.0,
        "burst_count": 2.0,
    }
    region_weights = {"us-east": 1.2, "eu-west": 1.0}

    result = telemetry_triage_pipeline(events, thresholds, region_weights)

    assert result["total_events"] == 3
    assert result["rejected_events"] == ["e4"]
    assert result["critical_events"][0]["event_id"] == "e2"
    assert result["high_events"][0]["event_id"] == "e1"
    assert len(result["service_health"]) == 2
    assert len(result["region_health"]) == 2
    assert result["tag_summary"][0] == {"tag": "db", "count": 2}
    assert "svc=api;" in result["digest"]
