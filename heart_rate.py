import time

class HeartRate:
	def __init__(self, frequency: int):
		self.__MOVING_AVERAGE_WINDOW: int = 5
		self.__ADAPTIVE_FACTOR: float = 0.8
		self.__PRESENCE_THRESHOLD: int = 10

		self.__frequency: int = frequency
		self.__timestamps: list = []
		self.__samples: list = []
		self.__filtered_samples: list = []
		self.__intervals: list = []	
		self.__heart_rate: int = 0
		self.__amplitudes: list = []
		
		self.__processed_window_size: int = self.__frequency

	def add_sample(self, sample: int) -> None:
		self.__timestamps.append(time.time())
		self.__samples.append(sample)
		
		if len(self.__samples) >= self.__MOVING_AVERAGE_WINDOW:
			filtered_sample = sum(self.__samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
			self.__filtered_samples.append(filtered_sample)
		else:
			self.__filtered_samples.append(sample)

		if len(self.__samples) > self.__processed_window_size:
			self.__samples.pop(0)
			self.__timestamps.pop(0)
			self.__filtered_samples.pop(0)
		
	def get(self) -> int:
		if not self.__presence():
			return -1
		return self.__calculate_heart_rate()
	
	def __presence(self) -> bool:
		if len(self.__filtered_samples) < self.__MOVING_AVERAGE_WINDOW:
			return False
		
		baseline = sum(self.__filtered_samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
		
		current_value = self.__filtered_samples[-1]
		amplitude = abs(current_value - baseline)

		self.__amplitudes.append(amplitude)
		if len(self.__amplitudes) > self.__processed_window_size:
			self.__amplitudes.pop(0)

		if len(self.__amplitudes) >= self.__MOVING_AVERAGE_WINDOW:
			filtered_amplitude = sum(self.__amplitudes[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
		else:
			filtered_amplitude = amplitude
		
		return filtered_amplitude > self.__PRESENCE_THRESHOLD

	def __peaks(self) -> list:
		peaks = []

		if len(self.__filtered_samples) < 3:
			return peaks
		
		if len(self.__intervals) >= self.__MOVING_AVERAGE_WINDOW:
			avg_interval = sum(self.__intervals[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
			min_interval = avg_interval * self.__ADAPTIVE_FACTOR
		else:
			min_interval = 0.3
		
		recent_samples = self.__filtered_samples[-self.__processed_window_size:]
		min_value = min(recent_samples)
		max_value = max(recent_samples)
		threshold = min_value + (max_value - min_value) * 0.5

		for i in range(1, len(self.__filtered_samples) - 1):
			if (
				self.__filtered_samples[i] > self.__filtered_samples[i - 1] and
				self.__filtered_samples[i] > self.__filtered_samples[i + 1] and
				self.__filtered_samples[i] > threshold
			):
				if peaks and self.__timestamps[i] - peaks[-1][0] < min_interval:
					if peaks[-1][1] < self.__filtered_samples[i]:
						peaks[-1] = (self.__timestamps[i], self.__filtered_samples[i])
				else:
					peaks.append((self.__timestamps[i], self.__filtered_samples[i]))
		
		return peaks

	def __calculate_heart_rate(self) -> int:
		peaks = self.__peaks()

		if len(peaks) < 2:
			return self.__heart_rate
		
		intervals = [peaks[i][0] - peaks[i - 1][0] for i in range(1, len(peaks))]
		self.__intervals.extend(intervals)
		self.__intervals = self.__intervals[-self.__processed_window_size:]

		if len(self.__intervals) > 1:
			average_interval = sum(self.__intervals) / len(self.__intervals)
			self.__heart_rate = int(60 / average_interval)
		
		return self.__heart_rate