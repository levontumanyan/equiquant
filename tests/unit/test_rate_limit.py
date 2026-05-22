import unittest
from unittest.mock import patch

from core.utils.rate_limit import RateLimitManager, TokenBucket


class TestRateLimit(unittest.TestCase):
	def test_token_bucket_refill(self):
		with patch("time.perf_counter") as mock_time:
			# Start at 0
			mock_time.return_value = 0.0
			# Capacity 2, refill 1 per second
			bucket = TokenBucket(capacity=2.0, refill_rate=1.0)

			# Consume all
			self.assertTrue(bucket.consume(1.0))
			self.assertTrue(bucket.consume(1.0))
			self.assertFalse(bucket.consume(0.1))  # Should be empty

			# Advance 0.6s, should have 0.6 tokens
			mock_time.return_value = 0.6
			self.assertTrue(bucket.consume(0.6))
			self.assertFalse(bucket.consume(0.1))

	def test_manager_buckets(self):
		manager = RateLimitManager()
		sec_bucket = manager.get_bucket("sec")
		fred_bucket = manager.get_bucket("fred")

		self.assertEqual(sec_bucket.capacity, 10.0)
		self.assertEqual(fred_bucket.refill_rate, 2.0)

		# Unknown provider gets default
		unknown = manager.get_bucket("unknown_api")
		self.assertEqual(unknown.capacity, 5.0)


if __name__ == "__main__":
	unittest.main()
