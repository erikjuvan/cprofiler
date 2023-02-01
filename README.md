# C Profiler for STM

Poor man's C profiler. It was written to time all functions duration in an STM32 application. 
It inserts a small snippet of code at the start and end of every function and then prints it out via UART.

Provided scripts:
1. automated_profiling.sh - run this, use -h,--help to see how to use it
2. add_profiler_code.py   - adds timing C code around every function body in the list of files provided to the 1. script
3. serial_to_file.py      - reads serial data for the duration of profiling
4. parse_profiler_data.py - parses data received from serial port