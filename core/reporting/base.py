from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseReporter(ABC):
	@abstractmethod
	def export(
		self, all_results: List[Dict[str, Any]], output_path: str, profile: str = "N/A"
	):
		"""Export results to the specified path."""
		pass
