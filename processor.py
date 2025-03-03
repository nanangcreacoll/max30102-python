import time

class Processor:
	"""
		Processor class for the MAX30102 sensor to calculate heart rate and oxygen saturation. 
	"""
	def __init__(self, frequency: int):
		self._MOVING_AVERAGE_WINDOW: int = 10
		self.__ADAPTIVE_FACTOR: float = 0.8
		self.__PRESENCE_THRESHOLD: int = 11

		self._frequency: int = frequency
		self._timestamps: list = []
		self._ir_samples: list = []
		self._red_samples: list = []
		self._filtered_ir_samples: list = []
		self._filtered_red_samples: list = []
		self._ratios: list = []
		self._intervals: list = []
		self._amplitudes: list = []

		self._processed_window_size: int = self._frequency
			
	def _add_sample(self, ir_sample: int, red_sample: int) -> None:
		"""
			Add ir and red samples to the processor.
					
			Parameters:
				ir_sample (int): The IR sample from the MAX30102 sensor.
				red_sample (int): The RED sample from the MAX30102 sensor.

			Returns:
				None
		"""
		
		self._timestamps.append(time.time())
		self._ir_samples.append(ir_sample)
		self._red_samples.append(red_sample)

		if len(self._ir_samples) >= self._MOVING_AVERAGE_WINDOW:
			filtered_ir_sample = sum(self._ir_samples[-self._MOVING_AVERAGE_WINDOW:]) / self._MOVING_AVERAGE_WINDOW
			filtered_red_sample = sum(self._red_samples[-self._MOVING_AVERAGE_WINDOW:]) / self._MOVING_AVERAGE_WINDOW
			self._filtered_ir_samples.append(filtered_ir_sample)
			self._filtered_red_samples.append(filtered_red_sample)
		else:
			self._filtered_ir_samples.append(ir_sample)
			self._filtered_red_samples.append(red_sample)

		if len(self._ir_samples) > self._processed_window_size:
			self._ir_samples.pop(0)
			self._red_samples.pop(0)
			self._timestamps.pop(0)
			self._filtered_ir_samples.pop(0)
			self._filtered_red_samples.pop(0)

	def _presence(self) -> bool:
		"""
			Check if there is a presence of finger.

			Returns:
				bool: True if there is a presence of finger, False otherwise.
		"""
		if len(self._filtered_ir_samples) < self._MOVING_AVERAGE_WINDOW:
			return False

		baseline = sum(self._filtered_ir_samples[-self._MOVING_AVERAGE_WINDOW:]) / self._MOVING_AVERAGE_WINDOW

		current_value = self._filtered_ir_samples[-1]
		amplitude = abs(current_value - baseline)

		self._amplitudes.append(amplitude)
		if len(self._amplitudes) > self._processed_window_size:
			self._amplitudes.pop(0)

		if len(self._amplitudes) >= self._MOVING_AVERAGE_WINDOW:
			filtered_amplitude = sum(self._amplitudes[-self._MOVING_AVERAGE_WINDOW:]) / self._MOVING_AVERAGE_WINDOW
		else:
			filtered_amplitude = amplitude

		return filtered_amplitude > self.__PRESENCE_THRESHOLD
	
	def _peaks(self) -> list:
		"""
			Find the peaks in the signal.

			Returns:
				list(tuple): The peaks in the signal (timestamp, value).

			NOTE: The peaks are calculated based on the adaptive threshold.
		"""
		peaks = []

		if len(self._filtered_ir_samples) < 3:
			return peaks

		if len(self._intervals) >= self._MOVING_AVERAGE_WINDOW:
			avg_interval = sum(self._intervals[-self._MOVING_AVERAGE_WINDOW:]) / self._MOVING_AVERAGE_WINDOW
			min_interval = avg_interval * self.__ADAPTIVE_FACTOR
		else:
			min_interval = 0.3

		recent_samples = self._filtered_ir_samples
		min_value = min(recent_samples)
		max_value = max(recent_samples)
		threshold = min_value + (max_value - min_value) * 0.5

		for i in range(1, len(self._filtered_ir_samples) - 1):
			if (
				self._filtered_ir_samples[i] > self._filtered_ir_samples[i - 1] and
				self._filtered_ir_samples[i] > self._filtered_ir_samples[i + 1] and
				self._filtered_ir_samples[i] > threshold
			):
				if peaks and self._timestamps[i] - peaks[-1][0] < min_interval:
					if peaks[-1][1] < self._filtered_ir_samples[i]:
						peaks[-1] = (self._timestamps[i], self._filtered_ir_samples[i])
				else:
					peaks.append((self._timestamps[i], self._filtered_ir_samples[i]))

		return peaks