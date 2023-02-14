#!/usr/bin/python
import re
import argparse
import operator
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
    parser.add_argument('p', '--print-count-cond', help='e.g. -p >=3 will only print functions where number of function calls was greater than or equal to 3')

    args = parser.parse_args()
    return args


def get_variables_per_function(all_vars):
    vars_per_function = []
    for v in all_vars:
        var_name_suffix = v[v.rfind("_"):] # find last _ (to find _cnt, _accum)
        if var_name_suffix in vars_per_function:
            break
        vars_per_function.append(var_name_suffix)

    return vars_per_function


def parse_print_count_cond(cond):
    number = re.findall(r"\d+", cond)
    num = int(number[0])

    ops = {
        ">=": operator.ge,
        "=": operator.eq,
        "<=": operator.le,
        ">": operator.gt,
        "<": operator.lt
    }
    op = re.findall(r"\D+", cond)
    return num, ops[op[0]]


if __name__ == "__main__":

    args = parse_cmdline_arguments()

    # read variable names
    with open(args.variables_file) as f:
        variables = []
        for line in f:
            variables.append(line.replace("\n",""))

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
    variables_and_data = []
    if len(data[len(data) - 1]) == 0:
        data.pop()
    if len(data) == len(variables):
        for i in range(len(data)):
            variables_and_data.append([variables[i], int(data[i])])
    else:
        print("data {data} / variables {var} length mismatch".format(data = len(data), var = len(variables)))

    vars_per_function = get_variables_per_function(variables)

    number_of_vars_per_function = len(vars_per_function)

    # generate a matrix
    vars_matrix = [variables_and_data[i:i+number_of_vars_per_function] for i in range(0, len(variables_and_data), number_of_vars_per_function)]

    top_row = "Function name"
    for v in vars_per_function:
        top_row += "," + v

    if args.print_count_cond is not None:
        count_condition_limit, count_condition_operator = parse_print_count_cond(args.print_count_cond)
    else:
        count_condition_limit = 0
        count_condition_operator = None

    # print all data (useful for direct import to excel)
    print(top_row)
    for lst in vars_matrix:

        if count_condition_operator != None:
            if count_condition_operator(lst[0][1], count_condition_limit):
                pass
            else:
                continue

        row = lst[0][0][:-len(vars_per_function[0])] # function name without suffix, extracted from first entry by removing the _suffix
        for i in range(number_of_vars_per_function):
            row += "," + str(lst[i][1])

        print(row)