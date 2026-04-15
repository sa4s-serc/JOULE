from __future__ import annotations

from typing import Any


def warehouse_balancing_pipeline(
    orders: list[dict[str, Any]],
    hub_capacities: dict[str, int],
    route_costs: dict[tuple[str, str], int],
) -> dict[str, Any]:
    normalized_orders: list[dict[str, Any]] = []
    skipped_orders: list[str] = []
    seen_order_ids: list[str] = []

    for raw_order in orders:
        raw_id = str(raw_order.get("order_id", "")).strip()
        if not raw_id:
            skipped_orders.append("missing-order-id")
            continue
        if raw_id in seen_order_ids:
            skipped_orders.append(raw_id)
            continue
        seen_order_ids.append(raw_id)

        source = str(raw_order.get("source", "UNKNOWN")).strip().upper() or "UNKNOWN"
        destination = str(raw_order.get("destination", "UNKNOWN")).strip().upper() or "UNKNOWN"
        sku = str(raw_order.get("sku", "unclassified")).strip().lower() or "unclassified"

        quantity_raw = raw_order.get("quantity", 0)
        if isinstance(quantity_raw, bool):
            quantity = 0
        elif isinstance(quantity_raw, int):
            quantity = quantity_raw
        elif isinstance(quantity_raw, float):
            quantity = int(quantity_raw)
        else:
            quantity = 0

        priority = str(raw_order.get("priority", "normal")).strip().lower()
        if priority not in {"low", "normal", "high", "critical"}:
            priority = "normal"

        preferred_hub = str(raw_order.get("preferred_hub", "")).strip().upper()
        if not preferred_hub:
            preferred_hub = source if source in hub_capacities else "OVERFLOW"

        if quantity < 0:
            quantity = 0

        normalized_orders.append(
            {
                "order_id": raw_id,
                "source": source,
                "destination": destination,
                "sku": sku,
                "quantity": quantity,
                "priority": priority,
                "preferred_hub": preferred_hub,
            }
        )

    orders_by_hub: dict[str, list[dict[str, Any]]] = {}
    for hub in hub_capacities:
        normalized_hub = hub.strip().upper()
        if normalized_hub not in orders_by_hub:
            orders_by_hub[normalized_hub] = []

    if "OVERFLOW" not in orders_by_hub:
        orders_by_hub["OVERFLOW"] = []

    for order in normalized_orders:
        hub = str(order["preferred_hub"])
        if hub not in orders_by_hub:
            orders_by_hub[hub] = []
        orders_by_hub[hub].append(order)

    priority_rank = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    for hub_name, queue in list(orders_by_hub.items()):
        sorted_queue = sorted(
            queue,
            key=lambda item: (
                priority_rank.get(str(item["priority"]), 2),
                -int(item["quantity"]),
                str(item["order_id"]),
            ),
        )
        orders_by_hub[hub_name] = sorted_queue

    remaining_capacity: dict[str, int] = {}
    for hub, cap in hub_capacities.items():
        sanitized_hub = hub.strip().upper()
        if cap < 0:
            remaining_capacity[sanitized_hub] = 0
        else:
            remaining_capacity[sanitized_hub] = cap

    if "OVERFLOW" not in remaining_capacity:
        remaining_capacity["OVERFLOW"] = 10**9

    assignments: list[dict[str, Any]] = []
    unassigned_order_ids: list[str] = []
    hub_loads: dict[str, int] = {}
    route_totals: dict[str, int] = {}
    sku_totals: dict[str, int] = {}
    source_totals: dict[str, int] = {}
    destination_totals: dict[str, int] = {}

    for hub_name, queue in orders_by_hub.items():
        for order in queue:
            order_id = str(order["order_id"])
            quantity = int(order["quantity"])
            source = str(order["source"])
            destination = str(order["destination"])
            sku = str(order["sku"])
            priority = str(order["priority"])

            selected_hub = hub_name
            if selected_hub != "OVERFLOW":
                available = remaining_capacity.get(selected_hub, 0)
                if available < quantity:
                    fallback_hub = "OVERFLOW"
                    best_capacity = -1
                    for candidate_hub, candidate_capacity in remaining_capacity.items():
                        if candidate_hub == "OVERFLOW":
                            continue
                        if candidate_capacity < quantity:
                            continue
                        if candidate_capacity > best_capacity:
                            best_capacity = candidate_capacity
                            fallback_hub = candidate_hub
                    selected_hub = fallback_hub

            if selected_hub != "OVERFLOW":
                if remaining_capacity.get(selected_hub, 0) >= quantity:
                    remaining_capacity[selected_hub] = remaining_capacity.get(selected_hub, 0) - quantity
                else:
                    selected_hub = "OVERFLOW"

            if selected_hub == "OVERFLOW":
                unassigned_order_ids.append(order_id)

            assignment: dict[str, Any] = {
                "order_id": order_id,
                "source": source,
                "destination": destination,
                "sku": sku,
                "quantity": quantity,
                "priority": priority,
                "assigned_hub": selected_hub,
            }
            assignments.append(assignment)

            if selected_hub not in hub_loads:
                hub_loads[selected_hub] = 0
            hub_loads[selected_hub] += quantity

            if sku not in sku_totals:
                sku_totals[sku] = 0
            sku_totals[sku] += quantity

            if source not in source_totals:
                source_totals[source] = 0
            source_totals[source] += quantity

            if destination not in destination_totals:
                destination_totals[destination] = 0
            destination_totals[destination] += quantity

            route_key = source + "->" + destination
            if route_key not in route_totals:
                route_totals[route_key] = 0

            direct_route = (source, destination)
            reverse_route = (destination, source)
            if direct_route in route_costs:
                per_unit_cost = route_costs[direct_route]
            elif reverse_route in route_costs:
                per_unit_cost = route_costs[reverse_route] + 1
            else:
                per_unit_cost = 5 + (len(source) % 4) + (len(destination) % 4)
            route_totals[route_key] += per_unit_cost * quantity

    hub_pressure: dict[str, float] = {}
    for hub_name, load in hub_loads.items():
        if hub_name == "OVERFLOW":
            continue
        baseline_capacity = remaining_capacity.get(hub_name, 0) + load
        if baseline_capacity <= 0:
            hub_pressure[hub_name] = 1.0
            continue
        hub_pressure[hub_name] = load / baseline_capacity

    pressure_flags: list[str] = []
    for hub_name, pressure in hub_pressure.items():
        if pressure >= 0.9:
            pressure_flags.append(hub_name + ":critical")
        elif pressure >= 0.75:
            pressure_flags.append(hub_name + ":high")
        elif pressure >= 0.55:
            pressure_flags.append(hub_name + ":medium")

    dominant_routes = sorted(route_totals.items(), key=lambda item: item[1], reverse=True)
    top_routes: list[dict[str, Any]] = []
    for route_name, route_cost in dominant_routes[:5]:
        top_routes.append({"route": route_name, "cost": route_cost})

    dominant_skus = sorted(sku_totals.items(), key=lambda item: item[1], reverse=True)
    top_skus: list[dict[str, Any]] = []
    for sku_name, quantity in dominant_skus[:5]:
        top_skus.append({"sku": sku_name, "quantity": quantity})

    operational_digest = ""
    for hub_name in sorted(hub_loads.keys()):
        operational_digest += "hub=" + hub_name + ";"
        operational_digest += "load=" + str(hub_loads[hub_name]) + ";"
        if hub_name in remaining_capacity:
            operational_digest += "remaining=" + str(remaining_capacity[hub_name]) + ";"
        else:
            operational_digest += "remaining=na;"

        if hub_name in hub_pressure:
            operational_digest += "pressure=" + f"{hub_pressure[hub_name]:.3f}" + ";"
        else:
            operational_digest += "pressure=na;"

        route_count = 0
        route_cost_sum = 0
        for assignment in assignments:
            if assignment["assigned_hub"] != hub_name:
                continue
            route_label = str(assignment["source"]) + "->" + str(assignment["destination"])
            if route_label in route_totals:
                route_count += 1
                route_cost_sum += route_totals[route_label]
        operational_digest += "routes=" + str(route_count) + ";"
        operational_digest += "route_cost_sum=" + str(route_cost_sum) + ";"

    priority_totals: dict[str, int] = {}
    for assignment in assignments:
        priority = str(assignment["priority"])
        if priority not in priority_totals:
            priority_totals[priority] = 0
        priority_totals[priority] += int(assignment["quantity"])

    priority_mix: list[dict[str, Any]] = []
    for priority_name in ["critical", "high", "normal", "low"]:
        if priority_name not in priority_totals:
            continue
        priority_mix.append({"priority": priority_name, "quantity": priority_totals[priority_name]})

    source_destination_pressure: list[dict[str, Any]] = []
    for source_name, source_qty in sorted(source_totals.items()):
        destination_qty = destination_totals.get(source_name, 0)
        if source_qty <= 0:
            pressure_ratio = 0.0
        else:
            pressure_ratio = destination_qty / source_qty
        source_destination_pressure.append(
            {
                "location": source_name,
                "outbound": source_qty,
                "inbound": destination_qty,
                "ratio": round(pressure_ratio, 4),
            }
        )

    return {
        "total_orders": len(assignments),
        "skipped_orders": skipped_orders,
        "unassigned_order_ids": sorted(unassigned_order_ids),
        "hub_loads": hub_loads,
        "remaining_capacity": remaining_capacity,
        "hub_pressure": hub_pressure,
        "pressure_flags": sorted(pressure_flags),
        "top_routes": top_routes,
        "top_skus": top_skus,
        "priority_mix": priority_mix,
        "source_destination_pressure": source_destination_pressure,
        "operational_digest": operational_digest,
    }


def telemetry_triage_pipeline(
    events: list[dict[str, Any]],
    thresholds: dict[str, float],
    region_weights: dict[str, float],
) -> dict[str, Any]:
    normalized_events: list[dict[str, Any]] = []
    rejected_events: list[str] = []

    for offset, event in enumerate(events):
        event_id = str(event.get("event_id", "")).strip()
        if not event_id:
            event_id = "auto-" + str(offset)

        service = str(event.get("service", "unknown-service")).strip().lower() or "unknown-service"
        region = str(event.get("region", "global")).strip().lower() or "global"

        latency_raw = event.get("latency_ms", 0.0)
        if isinstance(latency_raw, bool):
            latency_ms = 0.0
        elif isinstance(latency_raw, int):
            latency_ms = float(latency_raw)
        elif isinstance(latency_raw, float):
            latency_ms = latency_raw
        else:
            latency_ms = 0.0

        error_raw = event.get("error_count", 0)
        if isinstance(error_raw, bool):
            error_count = 0
        elif isinstance(error_raw, int):
            error_count = error_raw
        elif isinstance(error_raw, float):
            error_count = int(error_raw)
        else:
            error_count = 0

        throughput_raw = event.get("throughput", 0)
        if isinstance(throughput_raw, bool):
            throughput = 0
        elif isinstance(throughput_raw, int):
            throughput = throughput_raw
        elif isinstance(throughput_raw, float):
            throughput = int(throughput_raw)
        else:
            throughput = 0

        tags_raw = event.get("tags", [])
        if isinstance(tags_raw, list):
            normalized_tags: list[str] = []
            for tag in tags_raw:
                normalized_tag = str(tag).strip().lower()
                if normalized_tag and normalized_tag not in normalized_tags:
                    normalized_tags.append(normalized_tag)
        else:
            normalized_tags = []

        if latency_ms < 0 or error_count < 0 or throughput < 0:
            rejected_events.append(event_id)
            continue

        error_rate = 0.0
        if throughput > 0:
            error_rate = error_count / throughput

        normalized_events.append(
            {
                "event_id": event_id,
                "service": service,
                "region": region,
                "latency_ms": latency_ms,
                "error_count": error_count,
                "throughput": throughput,
                "error_rate": error_rate,
                "tags": normalized_tags,
            }
        )

    latency_threshold = float(thresholds.get("latency_ms", 180.0))
    error_rate_threshold = float(thresholds.get("error_rate", 0.08))
    throughput_threshold = float(thresholds.get("throughput", 80.0))
    burst_threshold = float(thresholds.get("burst_count", 5.0))

    service_windows: dict[str, list[float]] = {}
    service_totals: dict[str, dict[str, float]] = {}
    region_totals: dict[str, dict[str, float]] = {}
    tag_counts: dict[str, int] = {}
    event_scores: list[dict[str, Any]] = []

    for event in normalized_events:
        service = str(event["service"])
        region = str(event["region"])

        if service not in service_windows:
            service_windows[service] = []
        service_windows[service].append(float(event["latency_ms"]))
        if len(service_windows[service]) > 12:
            service_windows[service].pop(0)

        if service not in service_totals:
            service_totals[service] = {
                "count": 0.0,
                "latency_sum": 0.0,
                "error_sum": 0.0,
                "throughput_sum": 0.0,
                "max_latency": 0.0,
            }

        service_totals[service]["count"] += 1.0
        service_totals[service]["latency_sum"] += float(event["latency_ms"])
        service_totals[service]["error_sum"] += float(event["error_count"])
        service_totals[service]["throughput_sum"] += float(event["throughput"])
        if float(event["latency_ms"]) > service_totals[service]["max_latency"]:
            service_totals[service]["max_latency"] = float(event["latency_ms"])

        if region not in region_totals:
            region_totals[region] = {
                "count": 0.0,
                "latency_sum": 0.0,
                "error_sum": 0.0,
                "throughput_sum": 0.0,
            }

        region_totals[region]["count"] += 1.0
        region_totals[region]["latency_sum"] += float(event["latency_ms"])
        region_totals[region]["error_sum"] += float(event["error_count"])
        region_totals[region]["throughput_sum"] += float(event["throughput"])

        for tag in event["tags"]:
            if tag not in tag_counts:
                tag_counts[tag] = 0
            tag_counts[tag] += 1

        score = 0.0
        latency_ms = float(event["latency_ms"])
        error_rate = float(event["error_rate"])
        throughput_value = float(event["throughput"])

        if latency_ms > latency_threshold:
            score += 1.0 + ((latency_ms - latency_threshold) / max(1.0, latency_threshold))
        if error_rate > error_rate_threshold:
            score += 1.0 + ((error_rate - error_rate_threshold) * 10.0)
        if throughput_value < throughput_threshold:
            score += 1.0 + ((throughput_threshold - throughput_value) / max(1.0, throughput_threshold))

        recent_window = service_windows[service]
        if recent_window:
            rolling_sum = 0.0
            for window_value in recent_window:
                rolling_sum += window_value
            rolling_avg = rolling_sum / len(recent_window)
        else:
            rolling_avg = 0.0

        if rolling_avg > latency_threshold * 1.1:
            score += 0.8
        if len(recent_window) >= int(burst_threshold):
            over_count = 0
            for window_value in recent_window:
                if window_value > latency_threshold:
                    over_count += 1
            if over_count >= int(burst_threshold):
                score += 1.2

        weight = region_weights.get(region, 1.0)
        weighted_score = score * weight

        severity = "ok"
        if weighted_score >= 5.0:
            severity = "critical"
        elif weighted_score >= 3.2:
            severity = "high"
        elif weighted_score >= 1.8:
            severity = "medium"

        event_scores.append(
            {
                "event_id": event["event_id"],
                "service": service,
                "region": region,
                "score": round(weighted_score, 4),
                "severity": severity,
                "latency_ms": latency_ms,
                "error_rate": round(error_rate, 4),
                "throughput": throughput_value,
            }
        )

    service_health: list[dict[str, Any]] = []
    for service, stats in service_totals.items():
        count = max(1.0, stats["count"])
        avg_latency = stats["latency_sum"] / count
        avg_error_rate = 0.0
        if stats["throughput_sum"] > 0:
            avg_error_rate = stats["error_sum"] / stats["throughput_sum"]

        health_band = "healthy"
        if avg_latency > latency_threshold * 1.3 or avg_error_rate > error_rate_threshold * 2.0:
            health_band = "critical"
        elif avg_latency > latency_threshold * 1.15 or avg_error_rate > error_rate_threshold * 1.5:
            health_band = "degraded"
        elif avg_latency > latency_threshold or avg_error_rate > error_rate_threshold:
            health_band = "watch"

        service_health.append(
            {
                "service": service,
                "count": int(stats["count"]),
                "avg_latency": round(avg_latency, 4),
                "max_latency": round(stats["max_latency"], 4),
                "avg_error_rate": round(avg_error_rate, 6),
                "health": health_band,
            }
        )

    service_health.sort(key=lambda item: (item["health"], -item["avg_latency"], item["service"]))

    region_health: list[dict[str, Any]] = []
    for region, stats in region_totals.items():
        count = max(1.0, stats["count"])
        avg_latency = stats["latency_sum"] / count
        avg_throughput = stats["throughput_sum"] / count
        avg_error = stats["error_sum"] / count
        pressure = (avg_latency / max(1.0, latency_threshold)) + (avg_error / max(1.0, throughput_threshold))

        pressure_band = "stable"
        if pressure >= 2.8:
            pressure_band = "critical"
        elif pressure >= 2.0:
            pressure_band = "high"
        elif pressure >= 1.3:
            pressure_band = "watch"

        region_health.append(
            {
                "region": region,
                "avg_latency": round(avg_latency, 4),
                "avg_throughput": round(avg_throughput, 4),
                "avg_error": round(avg_error, 4),
                "pressure": round(pressure, 4),
                "band": pressure_band,
            }
        )

    region_health.sort(key=lambda item: (-item["pressure"], item["region"]))

    event_scores.sort(key=lambda item: (-item["score"], item["event_id"]))
    critical_events: list[dict[str, Any]] = []
    high_events: list[dict[str, Any]] = []
    medium_events: list[dict[str, Any]] = []

    for scored in event_scores:
        severity = str(scored["severity"])
        if severity == "critical":
            critical_events.append(scored)
        elif severity == "high":
            high_events.append(scored)
        elif severity == "medium":
            medium_events.append(scored)

    top_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)
    tag_summary: list[dict[str, Any]] = []
    for name, count in top_tags[:10]:
        tag_summary.append({"tag": name, "count": count})

    digest = ""
    for service_item in service_health:
        digest += "svc=" + str(service_item["service"]) + ";"
        digest += "health=" + str(service_item["health"]) + ";"
        digest += "avg_latency=" + str(service_item["avg_latency"]) + ";"
        digest += "avg_error_rate=" + str(service_item["avg_error_rate"]) + "|"

    for region_item in region_health:
        digest += "region=" + str(region_item["region"]) + ";"
        digest += "band=" + str(region_item["band"]) + ";"
        digest += "pressure=" + str(region_item["pressure"]) + "|"

    return {
        "total_events": len(normalized_events),
        "rejected_events": sorted(rejected_events),
        "service_health": service_health,
        "region_health": region_health,
        "critical_events": critical_events,
        "high_events": high_events,
        "medium_events": medium_events,
        "tag_summary": tag_summary,
        "digest": digest,
    }
