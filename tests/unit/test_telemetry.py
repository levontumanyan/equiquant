import threading
import time

from core.stats import InstrumentedLock, SessionStats


def test_session_stats_pooling():
	stats = SessionStats()
	stats.record_pool_submission()
	assert stats.pool_tasks_submitted == 1

	stats.record_task_start(0.5)
	assert stats.pool_active_workers == 1
	assert stats.pool_peak_workers == 1
	assert stats.pool_queued_time_total == 0.5

	stats.record_task_complete(1.0)
	assert stats.pool_active_workers == 0
	assert stats.pool_tasks_completed == 1
	assert stats.pool_worker_time_total == 1.0


def test_instrumented_lock_contention():
	stats = SessionStats()
	lock = InstrumentedLock("test_lock", stats)

	# Simple acquire
	with lock:
		pass

	# We can't easily force contention in a unit test without complex threading,
	# but we can check if it at least doesn't crash and records something if it waits.
	# We can simulate wait time if we mock the lock or just verify the method is called.

	stats.record_mutex_wait("test_lock", 0.1)
	data = stats.to_dict()
	assert data["threading"]["mutex_wait_time_total_s"] == 0.1
	assert data["threading"]["mutex_contention"]["test_lock"] == 0.1


def test_instrumented_lock_threaded_contention():
	stats = SessionStats()
	lock = InstrumentedLock("threaded_lock", stats)

	def worker():
		with lock:
			time.sleep(0.1)

	t1 = threading.Thread(target=worker)
	t2 = threading.Thread(target=worker)

	t1.start()
	time.sleep(0.05)  # Ensure t1 has the lock
	t2.start()

	t1.join()
	t2.join()

	# t2 must have waited at least 0.05s
	assert stats.mutex_wait_times["threaded_lock"] > 0.04
