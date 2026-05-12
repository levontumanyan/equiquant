import threading
import time
from typing import Dict, List, Set


class InstrumentedLock:
	def __init__(self, name: str, stats_instance: "SessionStats"):
		self._lock = threading.Lock()
		self.name = name
		self.stats = stats_instance

	def __enter__(self):
		start = time.perf_counter()
		self._lock.acquire()
		wait_time = time.perf_counter() - start
		if wait_time > 0:
			self.stats.record_mutex_wait(self.name, wait_time)
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self._lock.release()

	def acquire(self, blocking=True, timeout=-1):
		start = time.perf_counter()
		result = self._lock.acquire(blocking, timeout)
		if result:
			wait_time = time.perf_counter() - start
			if wait_time > 0:
				self.stats.record_mutex_wait(self.name, wait_time)
		return result

	def release(self):
		self._lock.release()


class SessionStats:
	def __init__(self):
		self._lock = threading.Lock()
		self.cache_hits = 0
		self.api_attempts = 0
		self.api_successes = 0
		self.http_requests = 0
		self.errors = 0
		self.stage_times: Dict[str, float] = {}
		self._stage_starts: Dict[str, float] = {}
		self.total_start_time = time.time()

		# New Telemetry fields
		self.endpoint_counts: Dict[str, int] = {}
		self.endpoint_latencies: Dict[str, List[float]] = {}
		self.io_time_total = 0.0
		self.scoring_time_total = 0.0
		self.cooldown_time_total = 0.0
		self.rate_limit_errors = 0
		self.artifacts: Set[str] = set()

		# Data Quality
		# metric_key -> { "present": int, "missing": int }
		self.data_coverage: Dict[str, Dict[str, int]] = {}

		# Error Topology
		# error_type -> count
		self.error_types: Dict[str, int] = {}
		self.retry_attempts = 0
		self.retry_successes = 0

		# Batching Efficiency
		self.bulk_fetch_symbols = 0
		self.fallback_fetch_symbols = 0

		# Resource Footprint
		self.initial_db_size = 0
		self.final_db_size = 0
		self.db_snapshots = 0
		self.total_tickers = 0
		self.analyzed_tickers = 0

		# Threading & Pooling
		self.pool_active_workers = 0
		self.pool_peak_workers = 0
		self.pool_tasks_submitted = 0
		self.pool_tasks_completed = 0
		self.pool_queued_time_total = 0.0
		self.pool_worker_time_total = 0.0

		# Contention
		self.mutex_wait_times: Dict[str, float] = {}
		self.session_fetches: Set[str] = set()

	@property
	def api_calls(self) -> int:
		"""Legacy support for api_calls property, maps to attempts."""
		with self._lock:
			return self.api_attempts

	@api_calls.setter
	def api_calls(self, value: int):
		with self._lock:
			self.api_attempts = value

	def start_stage(self, name: str):
		with self._lock:
			self._stage_starts[name] = time.time()

	def end_stage(self, name: str):
		with self._lock:
			if name in self._stage_starts:
				self.stage_times[name] = time.time() - self._stage_starts[name]

	def record_request(self, endpoint: str, duration: float, success: bool = True):
		"""Record an HTTP request with its endpoint and latency."""
		with self._lock:
			self.http_requests += 1
			self.endpoint_counts[endpoint] = self.endpoint_counts.get(endpoint, 0) + 1
			if endpoint not in self.endpoint_latencies:
				self.endpoint_latencies[endpoint] = []
			self.endpoint_latencies[endpoint].append(duration)
			self.io_time_total += duration

	def record_cooldown(self, duration: float):
		"""Record time spent in backpressure cooldown."""
		with self._lock:
			self.cooldown_time_total += duration

	def record_metric_coverage(self, metric_key: str, present: bool):
		"""Record whether a specific metric was found for an asset."""
		with self._lock:
			if metric_key not in self.data_coverage:
				self.data_coverage[metric_key] = {"present": 0, "missing": 0}
			if present:
				self.data_coverage[metric_key]["present"] += 1
			else:
				self.data_coverage[metric_key]["missing"] += 1

	def record_artifact(self, path: str):
		"""Record a file path created during the session."""
		with self._lock:
			self.artifacts.add(str(path))

	def record_error(self, error_type: str):
		"""Record a specific type of error."""
		with self._lock:
			self.errors += 1
			self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
			if error_type == "rate_limit":
				self.rate_limit_errors += 1

	def record_pool_submission(self):
		with self._lock:
			self.pool_tasks_submitted += 1

	def record_task_start(self, queued_time: float):
		with self._lock:
			self.pool_active_workers += 1
			self.pool_peak_workers = max(
				self.pool_peak_workers, self.pool_active_workers
			)
			self.pool_queued_time_total += queued_time

	def record_task_complete(self, worker_time: float):
		with self._lock:
			self.pool_active_workers -= 1
			self.pool_tasks_completed += 1
			self.pool_worker_time_total += worker_time

	def record_mutex_wait(self, name: str, duration: float):
		with self._lock:
			self.mutex_wait_times[name] = (
				self.mutex_wait_times.get(name, 0.0) + duration
			)

	def record_fetch(self, symbol: str):
		with self._lock:
			self.session_fetches.add(symbol.upper())

	def is_fetched(self, symbol: str) -> bool:
		with self._lock:
			return symbol.upper() in self.session_fetches

	def get_total_time(self) -> float:
		return time.time() - self.total_start_time

	def to_dict(self) -> Dict:
		"""Return the session statistics as a dictionary."""
		with self._lock:
			total_requests = self.cache_hits + self.api_attempts
			cache_rate = (
				(self.cache_hits / total_requests * 100) if total_requests > 0 else 0
			)

			endpoint_stats = {}
			for ep, latencies in self.endpoint_latencies.items():
				avg_lat = sum(latencies) / len(latencies) if latencies else 0
				endpoint_stats[ep] = {
					"count": self.endpoint_counts.get(ep, 0),
					"avg_latency_s": round(avg_lat, 3),
				}

			coverage_stats = {}
			for m, counts in self.data_coverage.items():
				total = counts["present"] + counts["missing"]
				density = (counts["present"] / total * 100) if total > 0 else 0
				coverage_stats[m] = round(density, 1)

			retry_rate = (
				(self.retry_successes / self.retry_attempts * 100)
				if self.retry_attempts > 0
				else 0
			)
			db_growth = max(0, self.final_db_size - self.initial_db_size)

			return {
				"total_tickers": self.total_tickers,
				"analyzed_tickers": self.analyzed_tickers,
				"threading": {
					"active_workers": self.pool_active_workers,
					"peak_workers": self.pool_peak_workers,
					"tasks_submitted": self.pool_tasks_submitted,
					"tasks_completed": self.pool_tasks_completed,
					"avg_queued_latency_s": round(
						self.pool_queued_time_total / self.pool_tasks_completed, 4
					)
					if self.pool_tasks_completed > 0
					else 0,
					"avg_worker_time_s": round(
						self.pool_worker_time_total / self.pool_tasks_completed, 4
					)
					if self.pool_tasks_completed > 0
					else 0,
					"total_worker_time_s": round(self.pool_worker_time_total, 2),
					"mutex_wait_time_total_s": round(
						sum(self.mutex_wait_times.values()), 4
					),
					"mutex_contention": {
						k: round(v, 4) for k, v in self.mutex_wait_times.items()
					},
				},
				"total_duration_s": round(self.get_total_time(), 2),
				"cache_hits": self.cache_hits,
				"api_attempts": self.api_attempts,
				"api_successes": self.api_successes,
				"cache_rate_pct": round(cache_rate, 2),
				"errors": self.errors,
				"error_types": self.error_types,
				"rate_limit_errors": self.rate_limit_errors,
				"retry_success_rate_pct": round(retry_rate, 2),
				"cooldown_time_s": round(self.cooldown_time_total, 2),
				"io_time_s": round(self.io_time_total, 2),
				"scoring_time_s": round(self.scoring_time_total, 2),
				"stage_durations_s": {
					k: round(v, 2) for k, v in self.stage_times.items()
				},
				"endpoints": endpoint_stats,
				"batching": {
					"bulk_symbols": self.bulk_fetch_symbols,
					"fallback_symbols": self.fallback_fetch_symbols,
					"bulk_ratio_pct": round(
						self.bulk_fetch_symbols
						/ (self.bulk_fetch_symbols + self.fallback_fetch_symbols)
						* 100,
						2,
					)
					if (self.bulk_fetch_symbols + self.fallback_fetch_symbols) > 0
					else 0,
				},
				"data_density_pct": coverage_stats,
				"resource_footprint": {
					"db_growth_bytes": db_growth,
					"db_final_size_bytes": self.final_db_size,
					"db_snapshots": self.db_snapshots,
				},
				"artifacts": list(self.artifacts),
			}


# Global instance for tracking the current execution run
stats = SessionStats()
