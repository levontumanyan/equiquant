from core.ui.terminal import (
	display_individual_results,
	display_summary_table,
	get_color_for_pct,
)


def test_get_color_for_pct():
	assert "green" in get_color_for_pct(0.95)
	assert "yellow" in get_color_for_pct(0.5)
	assert "red" in get_color_for_pct(0.2)


def test_display_individual_results(mocker):
	mock_console = mocker.patch("core.ui.terminal.console.print")

	results = [
		{
			"name": "Metric1",
			"value": "10.0",
			"status": "80%",
			"score": 1.0,
			"weight": 1.0,
			"pct": 0.8,
		}
	]
	benchmark_defs = [{"name": "Metric1"}]

	display_individual_results("AAPL", "Apple", results, benchmark_defs)
	assert mock_console.called


def test_display_summary_table(mocker):
	mock_console = mocker.patch("core.ui.terminal.console.print")

	results = [
		{"symbol": "AAPL", "name": "Apple", "score": 85.0},
		{"symbol": "MSFT", "name": "Microsoft", "score": 45.0},
	]

	display_summary_table(results)
	assert mock_console.called
