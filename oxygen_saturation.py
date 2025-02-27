from .processor import Processor

class OxygenSaturation(Processor):
	def __init__(self, frequency: int):
		super().__init__(frequency)
		self.__oxygen_saturation: int = 0

	def add_sample(self, ir_sample: int, red_sample: int) -> None:
		"""
			Add a sample to the oxygen saturation calculation.

			Parameters:
				ir_sample (int): The IR sample from the MAX30102 sensor.
				red_sample (int): The RED sample from the MAX30102 sensor.

			Returns:
				None

			NOTE: Add the IR and RED samples in loop with the sample rate of the sensor or without any delay.
		"""
		self._add_sample(ir_sample, red_sample)

		self.__oxygen_saturation = self.__calculate_oxygen_saturation()

	def get(self) -> int:
		"""
			Get the oxygen saturation

			Returns:
				int: The oxygen saturation in percentage.

			NOTE: Return -1 if the oxygen saturation is not available.
		"""
		if not self._presence():
			return -1
		return self.__oxygen_saturation

	def __calculate_oxygen_saturation(self) -> int:
		"""Calculate the oxygen saturation"""
		peaks = self._peaks()

		if len(peaks) < 2:
			return self.__oxygen_saturation
		
		intervals = [peaks[i][0] - peaks[i - 1][0] for i in range(1, len(peaks))]
		self._intervals.extend(intervals)
		self._intervals = self._intervals[-self._processed_window_size:]

		"""
			Ratio = (AC Red / DC Red) / (AC IR / DC IR)
		"""
		ratios = []
		for timestamp, peak in peaks:
			index = self._timestamps.index(timestamp)

			start_index = max(0, index - self._MOVING_AVERAGE_WINDOW)
			end_index = min(len(self._filtered_ir_samples), index + self._MOVING_AVERAGE_WINDOW)

			red_dc = sum(self._filtered_red_samples[start_index:end_index]) / (end_index - start_index)
			ir_dc = sum(self._filtered_ir_samples[start_index:end_index]) / (end_index - start_index)

			red_ac = self._filtered_red_samples[index] - red_dc
			ir_ac = self._filtered_ir_samples[index] - ir_dc

			if red_ac > 0 and ir_ac > 0:
				ratio = (red_ac / red_dc) / (ir_ac / ir_dc)
				ratios.append(ratio)
		
		self._ratios.extend(ratios)
		self._ratios = self._ratios[-self._processed_window_size:]

		if len(self._ratios) < 2:
			return self.__oxygen_saturation
		
		average_ratio = sum(self._ratios) / len(self._ratios)

		"""
			SpO2 = a * Ratio^2 / 10000 + b * Ratio / 100 + c
			a = -45.060
			b = 30.354
			c = 94.845
		"""
		self.__oxygen_saturation = int(-45.060 * ((average_ratio**2) / 10000.0) + 30.054 * (average_ratio / 100.0) + 94.845)
		
		return self.__oxygen_saturation