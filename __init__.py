import smbus
import time
from collections import deque

MAX30102_I2C_ADDRESS = 0x57

MAX30102_INT_STATUS_1 = 0x00
MAX30102_INT_STATUS_2 = 0x01
MAX30102_INT_ENABLE_1 = 0x02
MAX30102_INT_ENABLE_2 = 0x03

MAX30102_FIFO_WRITE_PTR = 0x04
MAX30102_FIFO_OVERFLOW_COUNTER = 0x05
MAX30102_FIFO_READ_PTR = 0x06
MAX30102_FIFO_DATA = 0x07

MAX30102_FIFO_CONFIG = 0x08
MAX30102_MODE_CONFIG = 0x09
MAX30102_SPO2_CONFIG = 0x0A
MAX30102_LED1_PULSE_AMPLITUDE = 0x0C
MAX30102_LED2_PULSE_AMPLITUDE = 0x0D
MAX30102_MULTI_LED_MODE_CONTROL1 = 0x11
MAX30102_MULTI_LED_MODE_CONTROL2 = 0x12

MAX30102_DIE_TEMP_INTERGER = 0x1F
MAX30102_DIE_TEMP_FRACTION = 0x20
MAX30102_DIE_TEMP_CONFIG = 0x21

MAX30102_REVISION_ID = 0xFE
MAX30102_PART_ID = 0xFF
MAX30102_EXPECTED_PART_ID = 0x15

MAX30102_SHUTDOWN_MASK = 0x7F
MAX30102_SHUTDOWN = 0x80
MAX30102_WAKEUP = 0x00
MAX30102_RESET_MASK = 0xBF
MAX30102_RESET = 0x40

MAX30102_MODE_MASK = 0xF8
MAX30102_MODE_RED_ONLY = 0x02 # Heart rate only
MAX30102_MODE_RED_IR_ONLY = 0x03 # SpO2 only
MAX30102_MODE_MULTI_LED = 0x07 # Multi-LED mode

MAX30102_READ_MODE_RED_ONLY = 3
MAX30102_READ_MODE_RED_IR_ONLY = MAX30102_READ_MODE_RED_ONLY * 2
MAX30102_READ_MODE_MULTI_LED = MAX30102_READ_MODE_RED_ONLY * 4

MAX30102_ROLLOVER_MASK = 0xEF
MAX30102_ROLLOVER_ENABLE = 0x10
MAX30102_ROLLOVER_DISABLE = 0x00
MAX30102_A_FULL_MASK = 0xF0

MAX30102_INT_DIE_TEMP_RDY_MASK = ~0b00000010
MAX30102_INT_DIE_TEMP_RDY_ENABLE = 0x02
MAX30102_INT_DIE_TEMP_RDY_DISABLE = 0x00

MAX30102_SAMPLE_AVG_MASK = ~0b11100000
MAX30102_SAMPLE_AVG_1 = 0x00
MAX30102_SAMPLE_AVG_2 = 0x20
MAX30102_SAMPLE_AVG_4 = 0x40
MAX30102_SAMPLE_AVG_8 = 0x60
MAX30102_SAMPLE_AVG_16 = 0x80
MAX30102_SAMPLE_AVG_32 = 0xA0

MAX30102_ADC_RANGE_MASK = 0x9F
MAX30102_ADC_RANGE_2048 = 0x00
MAX30102_ADC_RANGE_4096 = 0x20
MAX30102_ADC_RANGE_8192 = 0x40
MAX30102_ADC_RANGE_16384 = 0x60

MAX30102_SAMPLE_RATE_MASK = 0xE3
MAX30102_SAMPLE_RATE_50 = 0x00
MAX30102_SAMPLE_RATE_100 = 0x04
MAX30102_SAMPLE_RATE_200 = 0x08
MAX30102_SAMPLE_RATE_400 = 0x0C
MAX30102_SAMPLE_RATE_800 = 0x10
MAX30102_SAMPLE_RATE_1000 = 0x14
MAX30102_SAMPLE_RATE_1600 = 0x18
MAX30102_SAMPLE_RATE_3200 = 0x1C

MAX30102_PULSE_WIDTH_MASK = 0xFC
MAX30102_PULSE_WIDTH_69 = 0x00 # 15-bit resolution, 69us
MAX30102_PULSE_WIDTH_118 = 0x01 # 16-bit resolution, 118us
MAX30102_PULSE_WIDTH_215 = 0x02 # 17-bit resolution, 215us
MAX30102_PULSE_WIDTH_411 = 0x03 # 18-bit resolution, 411us

MAX30102_PULSE_AMP_LOWEST = 0x02  # 0.4mA  - Presence detection of ~4 inch
MAX30102_PULSE_AMP_LOW = 0x1F  # 6.4mA  - Presence detection of ~8 inch
MAX30102_PULSE_AMP_MEDIUM = 0x7F  # 25.4mA - Presence detection of ~8 inch
MAX30102_PULSE_AMP_HIGH = 0xFF  # 50.0mA - Presence detection of ~12 inch

MAX30102_SLOT1_MASK = 0xF8
MAX30102_SLOT2_MASK = 0x8F
MAX30102_SLOT3_MASK = 0xF8
MAX30102_SLOT4_MASK = 0x8F

SLOT_NONE = 0x00
SLOT_RED_LED = 0x01
SLOT_IR_LED = 0x02

STORAGE_QUEUE_SIZE = 4

class MAX30102:
	def __init__(self, i2c: smbus.SMBus, address: int = MAX30102_I2C_ADDRESS):
		self.__i2c: smbus.SMBus = i2c
		self.__address: int = address

		self.__active_leds = None
		self.__multi_led_read_mode = None
		self.__sample_rate = None
		self.__pulse_width = None
		self.__sample_average = None

		self.__acquisition_frequency = None
		self.__acquisition_frequency_inverse = None

		self.__sensor_data = self.SensorData()

	def __del__(self):
		self.shutdown()

	class CircularBuffer(object):
		"""
			Simple circular buffer implementation.
		"""
		def __init__(self, max_size):
			self.data = deque((), max_size)
			self.max_size = max_size

		def __len__(self):
			return len(self.data)

		def is_empty(self):
			return not bool(self.data)

		def append(self, item):
			try:
				self.data.append(item)
			except IndexError:
				self.data.popleft()
				self.data.append(item)

		def pop(self):
			return self.data.popleft()

		def clear(self):
			self.data = deque((), self.max_size)

		def pop_head(self):
			buffer_size = len(self.data)
			temp = deque(self.data)
			if buffer_size == 1:
				pass
			elif buffer_size > 1:
				self.data.clear()
				for x in range(buffer_size - 1):
					self.data = temp.popleft()
			else:
				return 0
			return temp.popleft()

	class SensorData:
		"""
			Structure to store the sensor data.
		"""
		def __init__(self):
			self.red = MAX30102.CircularBuffer(STORAGE_QUEUE_SIZE)
			self.ir = MAX30102.CircularBuffer(STORAGE_QUEUE_SIZE)

	def get_address(self) -> int:
		"""
			Get the I2C address of the MAX30102 sensor.

			Returns:
				int: The I2C address of the sensor.
		"""
		return self.__address

	def setup_sensor(self, 
				  sample_rate: int = MAX30102_SAMPLE_RATE_400,
				  led_mode: int = MAX30102_MODE_RED_IR_ONLY,
				  adc_range: int = MAX30102_ADC_RANGE_16384,
				  sample_avg: int = MAX30102_SAMPLE_AVG_8,
				  pulse_width: int = MAX30102_PULSE_WIDTH_411,
				  pulse_amplitude: int = MAX30102_PULSE_AMP_MEDIUM,
	) -> None:
		"""
			Setup the MAX30102 sensor.
			
			Parameters:
				sample_rate (int): The sample rate of the sensor.
				led_mode (int): The mode of the LED.
				adc_range (int): The ADC range of the sensor.
				sample_avg (int): The sample average of the sensor.
				pulse_width (int): The pulse width of the sensor.
				pulse_amplitude (int): The pulse amplitude of the sensor.

			Returns:
				None

			NOTE: The default values are set to the recommended values for heart rate and SpO2 measurement.
		"""
		self.soft_reset()
		self.set_fifo_average(sample_avg)
		self.enable_fifo_rollover()
		self.set_led_mode(led_mode)
		self.set_adc_range(adc_range)
		self.set_sample_rate(sample_rate)
		self.set_pulse_width(pulse_width)
		self.set_led_pulse_amplitude_red(pulse_amplitude)
		self.set_led_pulse_amplitude_ir(pulse_amplitude)
		self.clear_fifo()

	def soft_reset(self, timeout: float = 1.0) -> None:
		"""
			Soft reset the MAX30102 sensor.

			Parameters:
				timeout (float): The timeout for the reset operation.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_RESET_MASK, MAX30102_RESET)
		start_time = time.time()
		reset_status = -1
		while not ((reset_status & MAX30102_RESET) == 0):
			if time.time() - start_time > timeout:
				raise TimeoutError("Soft reset timeout.")
			time.sleep(0.01)
			reset_status = self.__i2c_read_reg(MAX30102_MODE_CONFIG)[0]

	def shutdown(self) -> None:
		"""
			Shutdown the MAX30102 sensor.
			
			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_SHUTDOWN_MASK, MAX30102_SHUTDOWN)

	def wakeup(self) -> None:
		"""
			Wakeup the MAX30102 sensor.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_SHUTDOWN_MASK, MAX30102_WAKEUP)

	def read_temperature(self) -> float:
		"""
			Read the temperature from the MAX30102 sensor.

			Returns:
				float: The temperature in degree celsius.
		"""
		self.__i2c_write_reg(MAX30102_DIE_TEMP_CONFIG, 0x01)

		read = self.__i2c_read_reg(MAX30102_INT_STATUS_2)[0]
		time.sleep(0.1)
		while (read & MAX30102_INT_DIE_TEMP_RDY_MASK) > 0:
			read = self.__i2c_read_reg(MAX30102_INT_STATUS_2)[0]
			time.sleep(0.001)

		temp_int = self.__i2c_read_reg(MAX30102_DIE_TEMP_INTERGER)[0]
		temp_frac = self.__i2c_read_reg(MAX30102_DIE_TEMP_FRACTION)[0]

		return float(temp_int) + (float(temp_frac) * 0.0625)
	
	def available(self) -> bool:
		"""
			Check if the MAX30102 sensor has data available in the FIFO.

			Returns:
				bool: True if data is available, False otherwise.
		"""			
		read_pointer = self.get_read_pointer()
		write_pointer = self.get_write_pointer()

		if read_pointer != write_pointer:
			number_of_samples = write_pointer - read_pointer

			if number_of_samples < 0:
				number_of_samples += 32

			for i in range(number_of_samples):
				if self.__multi_led_read_mode is not None:
					fifo_bytes = self.__i2c_read_reg(MAX30102_FIFO_DATA, self.__multi_led_read_mode)

					if self.__active_leds is not None and self.__active_leds > 0:
						self.__sensor_data.red.append(self.__fifo_bytes_to_int(fifo_bytes[0:3]))
					if self.__active_leds is not None and self.__active_leds > MAX30102_MODE_RED_ONLY:
						self.__sensor_data.ir.append(self.__fifo_bytes_to_int(fifo_bytes[3:6]))
					if self.__active_leds is not None and self.__active_leds > MAX30102_MODE_RED_IR_ONLY:
						self.__sensor_data.red.append(self.__fifo_bytes_to_int(fifo_bytes[6:9]))
						self.__sensor_data.ir.append(self.__fifo_bytes_to_int(fifo_bytes[9:12]))

			return len(self.__sensor_data.red) > 0 or len(self.__sensor_data.ir) > 0
		else:
			return False

	def get_red(self) -> int:
		"""
			Get the Red LED data from the MAX30102 sensor.
			
			Returns:
				int: The Red LED data.
		"""
		return self.__pop_red_from_storage()
	
	def get_ir(self) -> int:
		"""
			Get the IR LED data from the MAX30102 sensor.
			
			Returns:
				int: The IR LED data.
		"""
		return self.__pop_ir_from_storage()
	
	def get_read_pointer(self) -> int:
		"""
			Get the read pointer of the FIFO from the MAX30102 sensor.

			Returns:
				int: The read pointer.
		"""
		return self.__i2c_read_reg(MAX30102_FIFO_READ_PTR)[0]
	
	def get_write_pointer(self) -> int:
		"""
			Get the write pointer of the FIFO from the MAX30102 sensor.

			Returns:
				int: The write pointer.
		"""
		return self.__i2c_read_reg(MAX30102_FIFO_WRITE_PTR)[0]

	def get_sample_rate(self) -> int:
		"""
			Get the sample rate of the MAX30102 sensor.

			Returns:
				int: The sample rate.
		"""
		return self.__sample_rate if self.__sample_rate is not None else 0
	
	def get_sample_avg(self) -> int:
		"""
			Get the sample average of the MAX30102 sensor.

			Returns:
				int: The sample average.
		"""
		return self.__sample_average if self.__sample_average is not None else 0

	def clear_fifo(self) -> None:
		"""
			Clear the FIFO of the MAX30102 sensor.

			Returns:
				None
		"""
		self.__i2c_write_reg(MAX30102_FIFO_WRITE_PTR, 0x00)
		self.__i2c_write_reg(MAX30102_FIFO_READ_PTR, 0x00)
		self.__i2c_write_reg(MAX30102_FIFO_OVERFLOW_COUNTER, 0x00)

	def enable_fifo_rollover(self) -> None:
		"""
			Enable the FIFO rollover of the MAX30102 sensor.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_ROLLOVER_MASK, MAX30102_ROLLOVER_ENABLE)

	def disable_fifo_rollover(self) -> None:
		"""
			Disable the FIFO rollover of the MAX30102 sensor.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_ROLLOVER_MASK, MAX30102_ROLLOVER_DISABLE)
	
	def enable_slot(self, slot_number: int, led: int) -> None:
		"""
			Enable the slot of the MAX30102 sensor.

			Parameters:
				slot_number (int): The slot number.
				led (int): The LED to be enabled.
			
			Returns:
				None
		"""
		if slot_number == 1:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL1, MAX30102_SLOT1_MASK, led)
		elif slot_number == 2:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL1, MAX30102_SLOT2_MASK, led << 4)
		elif slot_number == 3:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL2, MAX30102_SLOT3_MASK, led)
		elif slot_number == 4:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL2, MAX30102_SLOT4_MASK, led << 4)
		else:
			raise ValueError(f"Invalid slot number: {slot_number}")

	def disable_slot(self) -> None:
		"""
			Disable the slot of the MAX30102 sensor.

			Returns:
				None	
		"""
		self.__i2c_write_reg(MAX30102_MULTI_LED_MODE_CONTROL1, 0x00)
		self.__i2c_write_reg(MAX30102_MULTI_LED_MODE_CONTROL2, 0x00)

	def set_led_mode(self, mode: int) -> None:
		"""
			Set the LED mode of the MAX30102 sensor.

			Parameters:
				mode (int): The mode of the LED.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_MODE_MASK, mode)

		self.enable_slot(1, SLOT_RED_LED)
		self.__multi_led_read_mode = MAX30102_READ_MODE_RED_ONLY
		if mode > MAX30102_MODE_RED_ONLY:
			self.enable_slot(2, SLOT_IR_LED)
			self.__multi_led_read_mode = MAX30102_READ_MODE_RED_IR_ONLY
		if mode > MAX30102_MODE_RED_IR_ONLY:
			self.enable_slot(3, SLOT_RED_LED)
			self.enable_slot(4, SLOT_IR_LED)
			self.__multi_led_read_mode = MAX30102_READ_MODE_MULTI_LED

		self.__active_leds = mode

	def set_fifo_average(self, sample_avg: int) -> None:
		"""
			Set the sample average of the MAX30102 sensor.
			
			Parameters:
				sample_avg (int): The sample average.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_SAMPLE_AVG_MASK, sample_avg)

		if sample_avg == MAX30102_SAMPLE_AVG_1:
			self.__sample_average = 1
		elif sample_avg == MAX30102_SAMPLE_AVG_2:
			self.__sample_average = 2
		elif sample_avg == MAX30102_SAMPLE_AVG_4:
			self.__sample_average = 4
		elif sample_avg == MAX30102_SAMPLE_AVG_8:
			self.__sample_average = 8
		elif sample_avg == MAX30102_SAMPLE_AVG_16:
			self.__sample_average = 16
		elif sample_avg == MAX30102_SAMPLE_AVG_32:
			self.__sample_average = 32
		else:
			raise ValueError(f"Invalid sample average: {sample_avg}")

		self.update_acquisition_frequency()

	def set_sample_rate(self, sample_rate: int) -> None:
		"""
			Set the sample rate of the MAX30102 sensor.

			Parameters:
				sample_rate (int): The sample rate.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_SPO2_CONFIG, MAX30102_SAMPLE_RATE_MASK, sample_rate)

		if sample_rate == MAX30102_SAMPLE_RATE_50:
			self.__sample_rate = 50
		elif sample_rate == MAX30102_SAMPLE_RATE_100:
			self.__sample_rate = 100
		elif sample_rate == MAX30102_SAMPLE_RATE_200:
			self.__sample_rate = 200
		elif sample_rate == MAX30102_SAMPLE_RATE_400:
			self.__sample_rate = 400
		elif sample_rate == MAX30102_SAMPLE_RATE_800:
			self.__sample_rate = 800
		elif sample_rate == MAX30102_SAMPLE_RATE_1000:
			self.__sample_rate = 1000
		elif sample_rate == MAX30102_SAMPLE_RATE_1600:
			self.__sample_rate = 1600
		elif sample_rate == MAX30102_SAMPLE_RATE_3200:
			self.__sample_rate = 3200
		else:
			raise ValueError(f"Invalid sample rate: {sample_rate}")

		self.update_acquisition_frequency()

	def update_acquisition_frequency(self) -> None:
		"""
			Update the acquisition frequency of the MAX30102 sensor.

			Returns:
				None
		"""
		if self.__sample_rate is not None and self.__sample_average is not None:
			self.__acquisition_frequency = int(self.__sample_rate / self.__sample_average)
			
			from math import ceil
			self.__acquisition_frequency_inverse = int(ceil(1000 / self.__acquisition_frequency))

	def get_acquisition_frequency(self) -> int:
		"""
			Get the acquisition frequency of the MAX30102 sensor.

			Returns:
				int: The acquisition frequency from sample rate and sample average in Hz.

			NOTE: Return 0 if the acquisition frequency is not available.
		"""
		return self.__acquisition_frequency if self.__acquisition_frequency is not None else 0

	def set_fifo_almost_full(self, number_of_samples: int) -> None:
		"""
			Set the FIFO almost full of the MAX30102 sensor.

			Parameters:
				number_of_samples (int): The number of samples.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_A_FULL_MASK, number_of_samples)

	def set_adc_range(self, adc_range: int) -> None:
		"""
			Set the ADC range of the MAX30102 sensor.

			Parameters:
				adc_range (int): The ADC range.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_SPO2_CONFIG, MAX30102_ADC_RANGE_MASK, adc_range)

	def set_pulse_width(self, pulse_width: int) -> None:
		"""
			Set the pulse width of the MAX30102 sensor.

			Parameters:
				pulse_width (int): The pulse width.

			Returns:
				None
		"""
		self.__set_bitmask(MAX30102_SPO2_CONFIG, MAX30102_PULSE_WIDTH_MASK, pulse_width)

		if pulse_width == MAX30102_PULSE_WIDTH_69:
			self.__pulse_width = 69
		elif pulse_width == MAX30102_PULSE_WIDTH_118:
			self.__pulse_width = 118
		elif pulse_width == MAX30102_PULSE_WIDTH_215:
			self.__pulse_width = 215
		elif pulse_width == MAX30102_PULSE_WIDTH_411:
			self.__pulse_width = 411

	def set_active_leds_amplitude(self, amplitude: int) -> None:
		"""
			Set the active LEDs amplitude of the MAX30102 sensor.

			Parameters:
				amplitude (int): The amplitude.

			Returns:
				None
		"""
		self.set_led_pulse_amplitude_red(amplitude)
		if self.__active_leds is not None and self.__active_leds > MAX30102_MODE_RED_ONLY:
			self.set_led_pulse_amplitude_ir(amplitude)

	def set_led_pulse_amplitude_red(self, amplitude: int) -> None:
		"""
			Set the Red LED pulse amplitude of the MAX30102 sensor.

			Parameters:
				amplitude (int): The amplitude from 0 to 255 (0x00 to 0xFF).

			Returns:
				None
		"""
		self.__i2c_write_reg(MAX30102_LED1_PULSE_AMPLITUDE, amplitude)

	def set_led_pulse_amplitude_ir(self, amplitude: int) -> None:
		"""
			Set the IR LED pulse amplitude of the MAX30102 sensor.

			Parameters:
				amplitude (int): The amplitude from 0 to 255 (0x00 to 0xFF).

			Returns:
				None
		"""
		self.__i2c_write_reg(MAX30102_LED2_PULSE_AMPLITUDE, amplitude)

	def read_part_id(self) -> int:
		"""
			Read the part ID of the MAX30102 sensor.

			Returns:
				int: The part ID.
		"""
		return self.__i2c_read_reg(MAX30102_PART_ID)[0]

	def check_part_id(self) -> bool:
		"""
			Check the part ID of the MAX30102 sensor.

			Returns:
				bool: True if the part ID is correct, False otherwise.
		"""
		return self.read_part_id() == MAX30102_EXPECTED_PART_ID
	
	def read_revision_id(self) -> int:
		"""
			Read the revision ID of the MAX30102 sensor.

			Returns:
				int: The revision ID.
		"""
		return self.__i2c_read_reg(MAX30102_REVISION_ID)[0]

	def __pop_red_from_storage(self) -> int:
		"""Pop the Red LED data from the storage."""
		if len(self.__sensor_data.red) == 0:
			return 0
		else:
			return self.__sensor_data.red.pop()
		
	def __pop_ir_from_storage(self) -> int:
		"""Pop the IR LED data from the storage."""
		if len(self.__sensor_data.ir) == 0:
			return 0
		else:
			return self.__sensor_data.ir.pop()

	def __fifo_bytes_to_int(self, fifo_bytes: list) -> int:
		"""Convert the FIFO bytes to integer."""
		return (fifo_bytes[0] << 16) | (fifo_bytes[1] << 8) | fifo_bytes[2]

	def __set_bitmask(self, reg: int, mask: int, value: int) -> None:
		"""Set the bitmask, read it, mask it, and write it."""
		data = (self.__i2c_read_reg(reg)[0] & mask) | value
		self.__i2c_write_reg(reg, data)

	def __bitmask(self, reg: int, mask: int, value: int) -> None:
		"""Bitmask the data and write it."""
		data = self.__i2c_read_reg(reg)[0]
		data = (data & mask) | value
		self.__i2c_write_reg(reg, data)

	def __i2c_read_reg(self, reg: int, length: int = 1) -> list:
		"""Read the I2C register."""
		return self.__i2c.read_i2c_block_data(self.__address, reg, length)

	def __i2c_write_reg(self, reg: int, data: int) -> None:
		"""Write the I2C register."""
		self.__i2c.write_i2c_block_data(self.__address, reg, [data])