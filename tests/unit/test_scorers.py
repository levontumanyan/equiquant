import math

import pytest

from core.scorers import (
	calculate_bell_score,
	calculate_linear_score,
	calculate_plateau_score,
	calculate_sigmoid_score,
	calculate_threshold_score,
)


def test_sigmoid_score():
	# Higher is better
	best, worst = 20.0, -10.0
	assert pytest.approx(calculate_sigmoid_score(20.0, best, worst), 0.01) == 0.95
	assert pytest.approx(calculate_sigmoid_score(-10.0, best, worst), 0.01) == 0.05
	assert pytest.approx(calculate_sigmoid_score(5.0, best, worst), 0.01) == 0.50

	# Outliers
	assert calculate_sigmoid_score(1000.0, best, worst) > 0.99
	assert calculate_sigmoid_score(-1000.0, best, worst) < 0.01

	# Lower is better
	best, worst = 10.0, 50.0
	assert pytest.approx(calculate_sigmoid_score(10.0, best, worst), 0.01) == 0.95
	assert pytest.approx(calculate_sigmoid_score(50.0, best, worst), 0.01) == 0.05
	assert pytest.approx(calculate_sigmoid_score(30.0, best, worst), 0.01) == 0.50


def test_linear_score():
	best, worst = 100, 0
	assert calculate_linear_score(100, best, worst) == 1.0
	assert calculate_linear_score(0, best, worst) == 0.0
	assert calculate_linear_score(50, best, worst) == 0.5
	assert calculate_linear_score(150, best, worst) == 1.0
	assert calculate_linear_score(-50, best, worst) == 0.0


def test_bell_score():
	target, width = 10.0, 2.0
	assert calculate_bell_score(10.0, target, width) == 1.0
	assert calculate_bell_score(12.0, target, width) == pytest.approx(math.exp(-0.5))
	assert calculate_bell_score(8.0, target, width) == pytest.approx(math.exp(-0.5))
	assert calculate_bell_score(100.0, target, width) < 0.01


def test_plateau_score():
	t_min, t_max, width = 5.0, 10.0, 2.0
	assert calculate_plateau_score(7.0, t_min, t_max, width) == 1.0
	assert calculate_plateau_score(5.0, t_min, t_max, width) == 1.0
	assert calculate_plateau_score(10.0, t_min, t_max, width) == 1.0

	# Decay below
	assert calculate_plateau_score(3.0, t_min, t_max, width) == pytest.approx(
		math.exp(-0.5)
	)
	# Decay above
	assert calculate_plateau_score(12.0, t_min, t_max, width) == pytest.approx(
		math.exp(-0.5)
	)

	assert calculate_plateau_score(-10.0, t_min, t_max, width) < 0.01
	assert calculate_plateau_score(25.0, t_min, t_max, width) < 0.01


def test_threshold_score():
	assert calculate_threshold_score(10, 5) == 1.0
	assert calculate_threshold_score(3, 5) == 0.0
	assert calculate_threshold_score(5, 5) == 1.0
