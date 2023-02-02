#!/usr/bin/python
import re
import argparse
from pprint import pprint

def parse_cmdline_arguments():
    """
    Parse command line arguments using argparse. Supports piped calls.
    Return namespace, with arguments as members. Can be converted to dictionary by calling vars(args).
    """
    parser = argparse.ArgumentParser(description='Parse data gathered from code added by add_profiler_code.py',
        epilog = 'Example: parse_profiler_data.py variables.txt data.txt')
    parser.add_argument('variables_file', help='File that contains the profiler variables')
    parser.add_argument('data_file', help='File that contains the profiler data')

    args = parser.parse_args()
    return args

args = parse_cmdline_arguments()

# read variable names
with open(args.variables_file) as f:
    variables = []
    for line in f:
        variables.append([line.replace("\n","")])

# extract lines containing data
start_pattern = re.compile(r'===START')
end_pattern = re.compile(r'===STOP')
start_found = False
extracted_lines = []
with open(args.data_file) as f:
    serial_data = f.readlines()

for line in serial_data:
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
if len(data) == len(variables):
    for i,v in enumerate(data):
        variables[i].append(int(v))
else:
    print("data {data} / variables {var} length mismatch".format(data = len(data), var = len(variables)))

number_of_vars = 2

# generate a matrix
vars_matrix = [variables[i:i+number_of_vars] for i in range(0, len(variables), number_of_vars)]

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