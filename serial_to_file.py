import serial
import sys

command_line_args = sys.argv
if not sys.stdin.isatty():
    command_line_args.extend(sys.stdin.readlines())

command_line_args.pop(0)

ser = serial.Serial(command_line_args[0], command_line_args[1])

with open("serial_data.txt", "w") as f:
    while True:
        data = ser.readline() # Read data from the serial port
        f.write(data) # Write data to file

ser.close() # Close the serial port