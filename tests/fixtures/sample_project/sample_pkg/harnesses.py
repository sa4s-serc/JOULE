def membership_harness(target) -> None:
    values = list(range(50)) * 50
    for _ in range(10):
        result = target(values)
        assert result > 0
