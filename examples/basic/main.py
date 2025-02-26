import smbus
import time
import board

import max30102
import max30102.heart_rate

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

	while True:
		if sensor.available():
			red_readings = sensor.get_red()
			ir_readings = sensor.get_ir()
			
			print(f"IR: {ir_readings}, RED: {red_readings}")

if __name__ == "__main__":
	main()