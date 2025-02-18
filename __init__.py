# This module is based on: https://github.com/n-elia/MAX30102-MicroPython-driver

import smbus
import time

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

MAX30102_ROLLOVER_MASK = 0xEF
MAX30102_ROLLOVER_ENABLE = 0x10
MAX30102_ROLLOVER_DISABLE = 0x00
MAX30102_A_FULL_MASK = 0xF0

MAX30102_SAMPLE_AVG_MASK = ~0b11100000
MAX30102_SAMPLE_AVG_1 = 0x00
MAX30102_SAMPLE_AVG_2 = 0x20
MAX30102_SAMPLE_AVG_4 = 0x40
MAX30102_SAMPLE_AVG_8 = 0x60
MAX30102_SAMPLE_AVG_16 = 0x80
MAX30102_SAMPLE_AVG_32 = 0xA0

MAX30102_ADC_RANGE_MASK = 0x9F
MAX30105_ADC_RANGE_2048 = 0x00
MAX30105_ADC_RANGE_4096 = 0x20
MAX30105_ADC_RANGE_8192 = 0x40
MAX30105_ADC_RANGE_16384 = 0x60

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

MAX30105_PULSE_AMP_LOWEST = 0x02  # 0.4mA  - Presence detection of ~4 inch
MAX30105_PULSE_AMP_LOW = 0x1F  # 6.4mA  - Presence detection of ~8 inch
MAX30105_PULSE_AMP_MEDIUM = 0x7F  # 25.4mA - Presence detection of ~8 inch
MAX30105_PULSE_AMP_HIGH = 0xFF  # 50.0mA - Presence detection of ~12 inch

MAX30102_SLOT1_MASK = 0xF8
MAX30102_SLOT2_MASK = 0x8F
MAX30102_SLOT3_MASK = 0xF8
MAX30102_SLOT4_MASK = 0x8F

SLOT_NONE = 0x00
SLOT_RED_LED = 0x01
SLOT_IR_LED = 0x02

class MAX30102:
	def __init__(self, i2c: smbus.SMBus, address: int = MAX30102_I2C_ADDRESS):
		self.__i2c = i2c
		self.__address = address

	def __del__(self):
		self.shutdown()

	def setup_sensor(self, 
				  sample_rate: int = MAX30102_SAMPLE_RATE_400,
				  led_mode: int = MAX30102_MODE_RED_IR_ONLY,
				  adc_range: int = MAX30105_ADC_RANGE_16384,
				  sample_avg: int = MAX30102_SAMPLE_AVG_8,
				  pulse_width: int = MAX30102_PULSE_WIDTH_411,
				  pulse_amplitude: int = MAX30105_PULSE_AMP_MEDIUM,
	) -> None:
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

	def soft_reset(self) -> None:
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_RESET_MASK, MAX30102_RESET)
		reset_status = -1
		while not ((reset_status & MAX30102_RESET) == 0):
			time.sleep(0.01)
			reset_status = self.__i2c_read_reg(MAX30102_MODE_CONFIG)[0]

	def shutdown(self) -> None:
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_SHUTDOWN_MASK, MAX30102_SHUTDOWN)

	def wakeup(self) -> None:
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_SHUTDOWN_MASK, MAX30102_WAKEUP)
	
	def clear_fifo(self) -> None:
		self.__i2c_write_reg(MAX30102_FIFO_WRITE_PTR, 0x00)
		self.__i2c_write_reg(MAX30102_FIFO_READ_PTR, 0x00)
		self.__i2c_write_reg(MAX30102_FIFO_OVERFLOW_COUNTER, 0x00)

	def enable_fifo_rollover(self) -> None:
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_ROLLOVER_MASK, MAX30102_ROLLOVER_ENABLE)

	def disable_fifo_rollover(self) -> None:
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_ROLLOVER_MASK, MAX30102_ROLLOVER_DISABLE)
	
	def enable_slot(self, slot_number: int, led: int) -> None:
		if slot_number == 1:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL1, MAX30102_SLOT1_MASK, led)
		elif slot_number == 2:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL1, MAX30102_SLOT2_MASK, led << 4)
		elif slot_number == 3:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL2, MAX30102_SLOT3_MASK, led)
		elif slot_number == 4:
			self.__bitmask(MAX30102_MULTI_LED_MODE_CONTROL2, MAX30102_SLOT4_MASK, led << 4)
		else:
			raise ValueError("Invalid slot number: {}".format(slot_number))

	def disable_slot(self) -> None:
		self.__i2c_write_reg(MAX30102_MULTI_LED_MODE_CONTROL1, 0x00)
		self.__i2c_write_reg(MAX30102_MULTI_LED_MODE_CONTROL2, 0x00)

	def set_led_mode(self, mode: int) -> None:
		self.__set_bitmask(MAX30102_MODE_CONFIG, MAX30102_MODE_MASK, mode)

		self.enable_slot(1, SLOT_RED_LED)
		if mode > MAX30102_MODE_RED_ONLY:
			self.enable_slot(2, SLOT_IR_LED)
		if mode > MAX30102_MODE_RED_IR_ONLY:
			self.enable_slot(3, SLOT_RED_LED)
			self.enable_slot(4, SLOT_IR_LED)

	def set_fifo_average(self, sample_avg: int) -> None:
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_SAMPLE_AVG_MASK, sample_avg)

	def set_fifo_almost_full(self, number_of_samples: int) -> None:
		self.__set_bitmask(MAX30102_FIFO_CONFIG, MAX30102_A_FULL_MASK, number_of_samples)

	def set_adc_range(self, adc_range: int) -> None:
		self.__set_bitmask(MAX30102_SPO2_CONFIG, MAX30102_ADC_RANGE_MASK, adc_range)

	def set_sample_rate(self, sample_rate: int) -> None:
		self.__set_bitmask(MAX30102_SPO2_CONFIG, MAX30102_SAMPLE_RATE_MASK, sample_rate)

	def set_pulse_width(self, pulse_width: int) -> None:
		self.__set_bitmask(MAX30102_SPO2_CONFIG, MAX30102_PULSE_WIDTH_MASK, pulse_width)

	def set_led_pulse_amplitude_red(self, amplitude: int) -> None:
		self.__i2c_write_reg(MAX30102_LED1_PULSE_AMPLITUDE, amplitude)

	def set_led_pulse_amplitude_ir(self, amplitude: int) -> None:
		self.__i2c_write_reg(MAX30102_LED2_PULSE_AMPLITUDE, amplitude)

	def read_part_id(self) -> int:
		return self.__i2c_read_reg(MAX30102_PART_ID)[0]

	def check_part_id(self) -> bool:
		return self.read_part_id() == MAX30102_EXPECTED_PART_ID
	
	def read_revision_id(self) -> int:
		return self.__i2c_read_reg(MAX30102_REVISION_ID)[0]

	def __set_bitmask(self, reg: int, mask: int, value: int) -> None:
		data = (self.__i2c_read_reg(reg)[0] & mask) | value
		self.__i2c_write_reg(reg, data)

	def __bitmask(self, reg: int, mask: int, value: int) -> None:
		data = self.__i2c_read_reg(reg)[0]
		data = (data & mask) | value
		self.__i2c_write_reg(reg, data)

	def __i2c_read_reg(self, reg: int, length: int = 1) -> list:
		return self.__i2c.read_i2c_block_data(self.__address, reg, length)

	def __i2c_write_reg(self, reg: int, data: int) -> None:
		self.__i2c.write_i2c_block_data(self.__address, reg, [data])