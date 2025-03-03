from .processor import Processor

class HeartRate(Processor):
	def __init__(self, frequency: int):
		super().__init__(frequency)
		self.__heart_rate: int = 0

	def add_sample(self, ir_sample: int, red_sample: int) -> None:
		"""
			Add a sample to the heart rate calculation.

			Parameters:
				ir_sample (int): The IR sample from the MAX30102 sensor.
				red_sample (int): The RED sample from the MAX30102 sensor.

			Returns:
				None

			NOTE: Add the IR and RED samples in loop with the sample rate of the sensor or without any delay.
		"""
		self._add_sample(ir_sample, red_sample)

		self.__heart_rate = self.__calculate_heart_rate()
		
	def get(self) -> int:
		"""
			Get the heart rate.

			Returns:
				int: The heart rate in bpm.

			NOTE: Return -1 if the heart rate is not available.
		"""
		if not self._presence():
			return -1
		return self.__heart_rate
	
	def __calculate_heart_rate(self) -> int:
		"""Calculate the heart rate based on the peaks intervals."""
		peaks = self._peaks()

		if len(peaks) < 2:
			return self.__heart_rate
		
		intervals = [peaks[i][0] - peaks[i - 1][0] for i in range(1, len(peaks))]
		self._intervals.extend(intervals)
		self._intervals = self._intervals[-self._processed_window_size:]

		if len(self._intervals) > 1:
			average_interval = sum(self._intervals[-self._MOVING_AVERAGE_WINDOW:]) / self._MOVING_AVERAGE_WINDOW
			return int(60 / average_interval)
		
		return self.__heart_rate