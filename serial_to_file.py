import serial
import sys

command_line_args = sys.argv
if not sys.stdin.isatty():
    command_line_args.extend(sys.stdin.readlines())

command_line_args.pop(0)

ser = serial.Serial(command_line_args[0], command_line_args[1])

with open("serial_data.txt", "w") as f:
    while True:
        data = ser.readline()
        try:
            decoded_data = data.decode(errors='ignore')
            f.write(decoded_data)
            f.flush()
            print(decoded_data)
            if "===END" in decoded_data:
                break
        except Exception as e:
            print("Error: {e}")

ser.close() # Close the serial port