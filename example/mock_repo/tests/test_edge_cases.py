from sample_pkg.edge_cases import impure_inventory_trace, nested_factory_total, recursive_inventory_checksum


def test_recursive_inventory_checksum() -> None:
    assert recursive_inventory_checksum([2, 4, 6, 8]) == 20


def test_nested_factory_total() -> None:
    assert nested_factory_total(6) == 45


def test_impure_inventory_trace(capsys) -> None:
    assert impure_inventory_trace([1, 2, 3]) == 6
    captured = capsys.readouterr()
    assert "computing inventory trace" in captured.out
