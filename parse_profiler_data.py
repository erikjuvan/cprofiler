#!/usr/bin/python
import sys
import re
import os
from pprint import pprint

command_line_args = sys.argv
if not sys.stdin.isatty():
    command_line_args.extend(sys.stdin.readlines())

command_line_args.pop(0)

if len(command_line_args) == 0:
    exit(0)

# read variable names
profiler_vars_filename = command_line_args[0]
with open(profiler_vars_filename) as f:
    vars = []
    for line in f:
        vars.append([line.replace("\n","")])

# extract lines containing data
start_pattern = re.compile(r'===START')
end_pattern = re.compile(r'===STOP')

profiler_data_filename = command_line_args[1]
with open(profiler_data_filename) as f:
    lines = f.readlines()

start_found = False
extracted_lines = []

for line in lines:
    if start_pattern.search(line):
        start_found = True
    elif end_pattern.search(line):
        start_found = False
    elif start_found:
        extracted_lines.append(line.replace("\n", ""))

data = "".join(extracted_lines)

data = data.split(",")
if len(data[len(data) - 1]) == 0:
    data.pop()
if len(data) == len(vars):
    for i,v in enumerate(data):
        vars[i].append(int(v))
else:
    print("data {data} / variables {var} length mismatch".format(data = len(data), var = len(vars)))

number_of_vars = 2

# generate a matrix
vars_matrix = [vars[i:i+number_of_vars] for i in range(0, len(vars), number_of_vars)]

# add avg field to matrix
for lst in vars_matrix:
    avg_str = lst[0][0][:-3] + "avg"
    if lst[0][1] == 0: # cnt == 0
        lst.append([avg_str, 0])
    else:
        lst.append([avg_str, lst[1][1] / lst[0][1]])

# # sort and print sorted (not used ATM since the lower print is more user friendly)
# sort_cnt = sorted(vars_matrix, key=lambda x: x[0][-1], reverse=True)
# sort_accum = sorted(vars_matrix, key=lambda x: x[1][-1], reverse=True)
# sort_avg = sorted(vars_matrix, key=lambda x: x[2][-1], reverse=True)
# print("\n\nCNT")
# pprint(sort_cnt[:100])
# print("\n\nACCUM")
# pprint(sort_accum[:100])
# print("AVERAGE")
# pprint(sort_avg[:100])

# print all data (useful for direct import to excel)
print("Function name,Call count,Accumulated time,Average time")
for lst in vars_matrix:
    func_str = lst[0][0][:-4]
    cnt = lst[0][1]
    accum = lst[1][1]
    avg = lst[2][1]
    print("{f},{c},{ac},{av}".format(f=func_str, c=cnt, ac=accum, av=avg))