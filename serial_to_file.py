import serial
import sys

command_line_args = sys.argv
if not sys.stdin.isatty():
    command_line_args.extend(sys.stdin.readlines())

command_line_args.pop(0)

ser = serial.Serial(command_line_args[0], command_line_args[1])

with open("serial_data.txt", "w") as f:
    while True:
        data = ser.read(size=1)
        try:
            decoded_data = data.decode(errors='ignore')
            f.write(decoded_data)
        except Exception as e:
            print(f"Error: {e}")

ser.close() # Close the serial port