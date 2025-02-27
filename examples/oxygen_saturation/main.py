import smbus
import time
import board

import max30102
import max30102.oxygen_saturation

bus = smbus.SMBus(1)
sensor = max30102.MAX30102(bus)

i2c = board.I2C()

def main():
	if sensor.get_address() not in i2c.scan():
		print("MAX30102 not found.")
		return
	elif not sensor.check_part_id():
		print("MAX30102 part ID not found.")
		return
	else:
		print("MAX30102 found.")

	sensor.setup_sensor()
	time.sleep(1)
	
	print(f"Reading temperature: {sensor.read_temperature()} °C")

	print("Starting data acquisition RED and IR")
	time.sleep(1)

	frequency = sensor.get_acquisition_frequency()
	if frequency is None or frequency == 0:
		print("Could not get acquisition frequency.")
		return
	
	oxygen_saturation = max30102.oxygen_saturation.OxygenSaturation(frequency)

	ref_time = time.time()
	while True:
		if sensor.available():
			ir_readings = sensor.get_ir()
			red_readings = sensor.get_red()
			
			oxygen_saturation.add_sample(ir_readings, red_readings)
			
		if time.time() - ref_time >= 1:
			print(f"Heart rate: {oxygen_saturation.get()} bpm")
			ref_time = time.time()

if __name__ == "__main__":
	main()