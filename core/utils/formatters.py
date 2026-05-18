def format_display_value(val: float, unit: str | None, is_decimal: bool = False) -> str:
	"""Format the value for human-readable display."""
	if unit == "percentage":
		return f"{val * 100:.2f}%" if is_decimal else f"{val:.2f}%"
	elif unit == "multiplier":
		return f"{val:.2f}x"
	elif unit == "currency":
		return f"${val:,.2f}"
	else:
		return f"{val:.2f}"
