"""The game starts, draws frames headless and exits cleanly."""

from overload.__main__ import main


def test_headless_run_exits_cleanly() -> None:
    assert main(["--headless", "--frames", "3"]) == 0
