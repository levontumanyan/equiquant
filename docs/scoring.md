# Scoring Methodologies

EquiQuant uses several mathematical models to score financial metrics, mapping raw data to a 0.0 - 1.0 "strength" scale.

- **Sigmoid Score**: An S-curve used for metrics where there is a "sweet spot" or where diminishing returns apply. Good for non-linear transitions.
- **Linear Score**: A simple proportional position between defined "best" and "worst" bounds.
- **Bell Curve Score**: Rewards values that cluster around a specific target (e.g., a target debt-to-equity ratio), penalizing both extremes.
- **Threshold Score**: A binary pass/fail mechanism for strict requirements.
