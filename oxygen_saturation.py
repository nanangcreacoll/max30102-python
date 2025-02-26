import time

class OxygenSaturation:
    def __init__(self, frequency: int):
        self.__MOVING_AVERAGE_WINDOW: int = 5
        self.__ADAPTIVE_FACTOR: float = 0.8
        self.__PRESENCE_THRESHOLD: int = 10

        self.__frequency: int = frequency
        self.__timestamps: list = []
        self.__ir_samples: list = []
        self.__red_samples: list = []
        self.__filtered_ir_samples: list = []
        self.__filtered_red_samples: list = []
        self.__ratios: list = []
        self.__intervals: list = []
        self.__oxygen_saturation: int = 0
        self.__amplitudes: list = []

        self.__processed_window_size: int = self.__frequency

    def add_sample(self, ir_sample: int, red_sample: int) -> None:
        self.__timestamps.append(time.time())
        self.__ir_samples.append(ir_sample)
        self.__red_samples.append(red_sample)

        if len(self.__ir_samples) >= self.__MOVING_AVERAGE_WINDOW:
            filtered_ir_sample = sum(self.__ir_samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
            filtered_red_sample = sum(self.__red_samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
            self.__filtered_ir_samples.append(filtered_ir_sample)
            self.__filtered_red_samples.append(filtered_red_sample)
        else:
            self.__filtered_ir_samples.append(ir_sample)
            self.__filtered_red_samples.append(red_sample)

        if len(self.__ir_samples) > self.__processed_window_size:
            self.__ir_samples.pop(0)
            self.__red_samples.pop(0)
            self.__timestamps.pop(0)
            self.__filtered_ir_samples.pop(0)
            self.__filtered_red_samples.pop(0)

        self.__oxygen_saturation = self.__calculate_oxygen_saturation()

    def get(self) -> int:
        if not self.__presence():
            return -1
        return self.__oxygen_saturation

    def __presence(self) -> bool:
        if len(self.__filtered_ir_samples) < self.__MOVING_AVERAGE_WINDOW:
            return False

        baseline = sum(self.__filtered_ir_samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW

        current_value = self.__filtered_ir_samples[-1]
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

        if len(self.__filtered_ir_samples) < 3:
            return peaks

        if len(self.__intervals) >= self.__MOVING_AVERAGE_WINDOW:
            avg_interval = sum(self.__intervals[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
            min_interval = avg_interval * self.__ADAPTIVE_FACTOR
        else:
            min_interval = 0.3

        recent_samples = self.__filtered_ir_samples
        min_value = min(recent_samples)
        max_value = max(recent_samples)
        threshold = min_value + (max_value - min_value) * 0.5

        for i in range(1, len(self.__filtered_ir_samples) - 1):
            if (
                self.__filtered_ir_samples[i] > self.__filtered_ir_samples[i - 1] and
                self.__filtered_ir_samples[i] > self.__filtered_ir_samples[i + 1] and
                self.__filtered_ir_samples[i] > threshold
            ):
                if peaks and self.__timestamps[i] - peaks[-1][0] < min_interval:
                    if peaks[-1][1] < self.__filtered_ir_samples[i]:
                        peaks[-1] = (self.__timestamps[i], self.__filtered_ir_samples[i])
                else:
                    peaks.append((self.__timestamps[i], self.__filtered_ir_samples[i]))

        return peaks
    
    def __calculate_oxygen_saturation(self) -> int:
        peaks = self.__peaks()

        if len(peaks) < 2:
            return self.__oxygen_saturation
        
        intervals = [peaks[i][0] - peaks[i - 1][0] for i in range(1, len(peaks))]
        self.__intervals.extend(intervals)
        self.__intervals = self.__intervals[-self.__processed_window_size:]

        ratios = []
        for timestamp, peak in peaks:
            index = self.__timestamps.index(timestamp)
            ac_red = self.__filtered_red_samples[index] - min(self.__filtered_red_samples)
            ac_ir = self.__filtered_ir_samples[index] - min(self.__filtered_ir_samples)
            dc_red = sum(self.__filtered_red_samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
            dc_ir = sum(self.__filtered_ir_samples[-self.__MOVING_AVERAGE_WINDOW:]) / self.__MOVING_AVERAGE_WINDOW
            
            if dc_ir != 0 and dc_red != 0:
                r = (ac_red / dc_red) / (ac_ir / dc_ir)
                ratios.append(r)
        
        self.__ratios.extend(ratios)
        self.__ratios = self.__ratios[-self.__processed_window_size:]

        if len(self.__ratios) < 2:
            return self.__oxygen_saturation
        
        average_ratio = sum(self.__ratios) / len(self.__ratios)

        if average_ratio > 0.02 and average_ratio < 1.84:
            self.__oxygen_saturation = int(-45.060 * (average_ratio**2) / 10000.0 + 30.054 * average_ratio / 100.0 + 94.845)
        
        return self.__oxygen_saturation