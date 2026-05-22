import logging
import threading
import time

logger = logging.getLogger(__name__)


class TokenBucket:
	"""
	Thread-safe implementation of the Token Bucket algorithm for rate limiting.
	"""

	def __init__(self, capacity: float, refill_rate: float):
		self.capacity = capacity
		self.refill_rate = refill_rate
		self.tokens = capacity
		self.last_refill = time.perf_counter()
		self._lock = threading.Lock()

	def consume(self, amount: float = 1.0) -> bool:
		with self._lock:
			now = time.perf_counter()
			# Refill tokens
			elapsed = now - self.last_refill
			self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
			self.last_refill = now

			if self.tokens >= amount:
				self.tokens -= amount
				return True
			return False

	def wait_for_token(self, amount: float = 1.0, timeout: float = 30.0):
		start_wait = time.perf_counter()
		while not self.consume(amount):
			if time.perf_counter() - start_wait > timeout:
				raise TimeoutError("Timeout waiting for rate limit token")
			time.sleep(0.1)


class RateLimitManager:
	"""
	Centralized manager for API rate limits across different providers.
	"""

	def __init__(self):
		self.buckets = {
			"sec": TokenBucket(capacity=10, refill_rate=10),  # 10 req/s
			"fred": TokenBucket(capacity=20, refill_rate=2.0),  # 120 req/m = 2 req/s
			"tiingo": TokenBucket(capacity=50, refill_rate=50 / 3600),  # 50 req/h
			"openbb": TokenBucket(capacity=5, refill_rate=1.0),  # Conservative default
		}
		self._lock = threading.Lock()

	def get_bucket(self, provider: str) -> TokenBucket:
		provider = provider.lower()
		with self._lock:
			if provider not in self.buckets:
				# Create a default bucket if unknown
				self.buckets[provider] = TokenBucket(capacity=5, refill_rate=0.5)
			return self.buckets[provider]


rate_limit_manager = RateLimitManager()
