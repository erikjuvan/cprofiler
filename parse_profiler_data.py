#!/usr/bin/python
import sys
import re
import os
from pprint import pprint

# read variable names
profiler_vars_filename = "profiler_vars.txt"
with open(profiler_vars_filename) as f:
    vars = []
    for line in f:
        vars.append([line.replace("\n","")])

# extract lines containing data
start_pattern = re.compile(r'=====BEGIN')
end_pattern = re.compile(r'=====END')

profiler_data_filename = "serial_data.txt"
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

# only look at the last entry, since it holds the most info
lines_of_interest = [extracted_lines[-1]]

# map data to variables
for l in lines_of_interest:
    data = l.split(",")
    if len(data[len(data) - 1]) == 0:
        data.pop()
    if len(data) == len(vars):
        for i,v in enumerate(data):
            vars[i].append(int(v))
    else:
        print("data {data} / variables {var} length mismatch".format(data = len(data), var = len(vars)))

# generate a matrix
vars_matrix = [vars[i:i+6] for i in range(0, len(vars), 6)]

# sort
sort_cnt = sorted(vars_matrix, key=lambda x: x[0][-1], reverse=True)
sort_avg = sorted(vars_matrix, key=lambda x: x[1][-1], reverse=True)

print("AVERAGE")
pprint(sort_avg[:10])
print("\n\nCNT")
pprint(sort_cnt[:10])