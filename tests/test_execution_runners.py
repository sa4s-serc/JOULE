from src.infrastructure.execution.runner import GreenGymRunner


class TestGreenGymRunner:

    def test_run_success(self):
        """Test successful execution of code and harness."""
        # Use a large timeout to avoid environmental slowness
        runner = GreenGymRunner(timeout_seconds=30)
        code = "def add(a, b): return a + b"
        test_code = "def test(): assert candidate.add(2, 2) == 4"

        success, metrics, output = runner.run(code, test_code)

        assert success is True
        assert "duration_seconds" in metrics

    def test_run_assertion_failure(self):
        """Test execution when harness assertion fails."""
        runner = GreenGymRunner(timeout_seconds=30)
        code = "def add(a, b): return a + b"
        test_code = "def test(): assert candidate.add(2, 2) == 5"

        success, metrics, output = runner.run(code, test_code)

        assert success is False
        assert "Assertion failed" in output or "AssertionError" in output

    def test_run_syntax_error(self):
        """Test execution when candidate has syntax error."""
        runner = GreenGymRunner(timeout_seconds=30)
        code = "def add(a, b: return a + b"  # Syntax error
        test_code = "def test(): pass"

        success, metrics, output = runner.run(code, test_code)

        assert success is False
        assert "SyntaxError" in output or "Exit code" in output

    def test_multiple_samples(self):
        """Test that multiple samples are run and aggregated."""
        runner = GreenGymRunner(timeout_seconds=30, samples=2)
        code = "def test(): return 1"
        test_code = "def test_fn(): assert candidate.test() == 1"

        success, metrics, output = runner.run(code, test_code)

        assert success is True
        assert "duration_seconds" in metrics

    def test_batch_execution(self):
        """Test parallel batch execution."""
        runner = GreenGymRunner(timeout_seconds=30, max_workers=2)
        candidates = [
            ("def a(): return 1", "def test(): assert candidate.a() == 1", "id1"),
            ("def b(): return 2", "def test(): assert candidate.b() == 2", "id2"),
        ]

        results = runner.run_batch(candidates)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True
