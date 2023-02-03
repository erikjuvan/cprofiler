#!/usr/bin/python

import sys
import re
import os
import argparse


def parse_cmdline_arguments():
    """
    Parse command line arguments using argparse. Supports piped calls.
    Return namespace, with arguments as members. Can be converted to dictionary by calling vars(args).
    """
    parser = argparse.ArgumentParser(description='Adds profiler code to supplied C source files',
        epilog='Example: add_profiler_code.py -c -e exclude_functions.txt file1.c file2.c file3.c')
    parser.add_argument("files", nargs="*", help='Files to be profiled')
    parser.add_argument('-c', '--count-only', action="store_true", help='Add only counter to profiled functions')
    parser.add_argument('-e', '--exclude-functions-file', help='Exclude functions provided in the file')
    parser.add_argument('-i', '--include-functions-file', help='Include only functions provided in the file')

    args = parser.parse_args()    
    # check if script is called from a pipe and extend the files argument with the contents
    if not sys.stdin.isatty():
        # remove empty strings
        stdin_list = list(filter(None, sys.stdin.read().splitlines()))
        # extend files argument with additional stdin
        args.files.extend(stdin_list)
    return args

# must be global function counter so it keeps count between files
function_counter = 0

def add_profiling_code_to_source_file(filename, count_only, exclude_functions_list, include_functions_list):
    global function_counter
    infilename = filename
    outfilename = filename + ".profiled"
    contents_list = []

    print(filename, end="")

    at_least_one_function_is_being_profiled = False # Used to not insert #include "profiler.h" if no function is being profiled

    #with open(filename, "r", encoding='unicode_escape') as infile, open(outfilename, "w") as outfile:
    with open(filename, "r") as infile:
        cnt  = 0
        func_name = ""
        func_start = ""
        func_end = ""
        added_variables = []

        # extract only file name from filename string so to not get common/app_c for a variable name, but instead only app_c
        match = re.search(r"([^\/]+$)", infilename)
        if match:
            infilename = match.group(1)

        infilename = infilename.replace(".", "_")

        lines_history = []
        write_func_end = False
        for line in infile:

            lines_history.append(line)

            # check if the line is a comment "//"
            match = re.search(r"^\s*\/\/", line)
            if match:
                contents_list.append(line)
                continue

            if "@{" in line or "@}" in line:
                contents_list.append(line)
                continue

            # case when "{}"
            if "{" in line and "}" in line:
                contents_list.append(line)
                continue

            if "{" in line:
                cnt += 1
                if cnt == 1:
                    match_found = False
                    prev_line_lookups = 0
                    for l in reversed(lines_history):

                        # check if the line contains an = sign
                        match = re.search(r"=", l)
                        if match:
                            break

                        # check if the line is a preprocessor directive "# "
                        match = re.search(r"^\s*#", l)
                        if match:
                            break

                        # check if the line is part of the preprocessor (last character is \)
                        match = re.search(r"\\$", l)
                        if match:
                            break

                        # check if the line contains an = sign
                        if "typedef" in l:
                            break

                        # remove any text following '{'
                        if "{" in l:
                            l = l[:l.index('{')]

                        # regex to find function name
                        match = re.search(r"\s*(\w+)\s*\([^(]*$", l)
                        if match:
                            if "sizeof" not in l: # if there is a match make sure it is not a sizeof function
                                match_found = True
                                break

                        # don't look more than n previous lines
                        prev_line_lookups += 1
                        if prev_line_lookups >= 7:
                            break

                    if match_found:
                        func_name = match.group(1)

                        # check if it is in the excluded functions list
                        if len(exclude_functions_list) > 0 and func_name in exclude_functions_list:
                            contents_list.append(line)
                            continue

                        # check if it is in the included functions list
                        if len(include_functions_list) > 0 and func_name not in include_functions_list:
                            contents_list.append(line)
                            continue

                        def make_var(name):
                            var_name = "_" + str(function_counter) + "_" + infilename + "_" + func_name + name
                            added_variables.append(var_name)
                            return var_name

                        # Increment function counter before creating variables so the count starts at 1
                        function_counter += 1

                        # if add only count
                        if count_only:
                            var_cnt = make_var("_cnt")
                            func_start = """    /// PROFILER ///
    profiler_vars.{vc}++;
    ////////////////\n\n""".format(vc = var_cnt)
                            func_end = ""

                        else:
                            var_cnt = make_var("_cnt")
                            var_accum = make_var("_accum")
                            func_start = """    /// PROFILER ///
    uint16_t _profiler_start = PROFILER_GET_US();
    ////////////////\n\n"""
                            func_end = """
    /// PROFILER ///
    if (profiler_running)
    {{
        profiler_vars.{vacc} += PROFILER_GET_ELAPSED_US(_profiler_start);
        profiler_vars.{vc}++;
    }}
    ////////////////\n""".format(vc = var_cnt, vacc = var_accum)

                        contents_list.append(line)
                        contents_list.append(func_start)
                        write_func_end = True
                        at_least_one_function_is_being_profiled = True
                        continue

            if "}" in line:
                cnt -= 1
                if cnt == 0 and write_func_end == True:
                    contents_list.append(func_end)
                    contents_list.append(line)
                    write_func_end = False
                    continue

            # also add func_end before every return statement (dooh, completely missed that one :P)
            match = re.search(r'(?<![a-zA-Z0-9_])return(?![a-zA-Z0-9_])', line)
            if match and write_func_end == True:
                contents_list.append(func_end)
                contents_list.append(line)
                continue

            contents_list.append(line)

    if at_least_one_function_is_being_profiled:
        contents_list.insert(0, "#include \"profiler.h\"\n\n")
        if len(include_functions_list) > 0:        
            print("    MATCH", end="")

    print("") # newline

    with open(outfilename, "w") as outfile:
        outfile.writelines(contents_list)

    os.replace(outfilename, filename)

    return added_variables


def create_profiler_source_and_header_files(list_of_added_variables, count_only):
    fprofiler_c = open("profiler.c", "w")

    profiler_c_src = """#include <stdint.h>
#include <string.h>
#include "trace.h"
#include "profiler.h"

char profiler_running = 0;

struct profiler_vars profiler_vars = {0};

static char _run_marker = 0;
static char _profiler_alive = 1;

typedef struct
{"""
    if count_only:
        profiler_c_src +="""
    uint32_t v;"""
    else:
        profiler_c_src +="""
        uint32_t v[2];"""
    profiler_c_src +="""
} prof_func_data;

static void _profiler_print(void)
{
    printf("===START %c\\n", _run_marker);
    // print all data
    int size = sizeof(profiler_vars) / sizeof(prof_func_data);
    prof_func_data *p = (prof_func_data *)&profiler_vars;
    for (int i = 0; i < size; ++i, ++p)
    {
        WWDG->CR = 127;
        IWDG->KR = 0x0000AAAAu;"""
    if count_only:
        profiler_c_src += """
        printf("%lu,", p->v);"""
    else:
        profiler_c_src += """
        printf("%lu,%lu,", p->v[0], p->v[1]);"""
    profiler_c_src += """
    }
    printf("\\n===STOP %c\\n", _run_marker);
}

// clear profiler_vars to 0
static void _profiler_memclear(void)
{
    memset(&profiler_vars, 0, sizeof(profiler_vars));
}

void profiler_start(char marker)
{
    if (_profiler_alive && !profiler_running && _run_marker == 0 && marker != 0)
    {
        printf("\\n%lu Profiler start %c\\n", PROFILER_GET_MS(), marker);
        _profiler_memclear();
        _run_marker = marker;
        profiler_running = 1;
    }
}

void profiler_stop(char marker)
{
    if (profiler_running && marker == _run_marker)
    {
        profiler_running = 0;
        printf("\\n%lu Profiler stop %c\\n", PROFILER_GET_MS(), marker);
        _profiler_print();
        _run_marker = 0;
    }
}

void profiler_end(void)
{
    if (_profiler_alive)
    {
        _profiler_alive = 0;
        profiler_stop(_run_marker);
        printf("===END\\n");
        printf("\\nProfiler end\\n");
    }
}

"""

    fprofiler_c.write(profiler_c_src)


    fprofiler_h = open("profiler.h", "w")

    profiler_h_src = """#pragma once

#include <stdint.h>
#include <stm32g0xx_hal.h>

#define PROFILER_GET_US() ((uint16_t)TIM7->CNT)
#define PROFILER_GET_ELAPSED_US(start) ((uint16_t)(PROFILER_GET_US() - (uint16_t)start))

#define PROFILER_GET_MS() ((uint32_t)TIM2->CNT)
#define PROFILER_GET_ELAPSED_MS(start) ((uint32_t)(PROFILER_GET_MS() - (uint32_t)start))

struct profiler_vars
{
"""

    for entry in list_of_added_variables:
        profiler_h_src += "    uint32_t " + entry + ";\n"

    profiler_h_src += "} profiler_vars;\n\n"

    profiler_h_src += """
extern char profiler_running;
extern struct profiler_vars profiler_vars;

void profiler_start(char marker);
void profiler_stop(char marker);
void profiler_end(void);

"""
    fprofiler_h.write(profiler_h_src)


def create_file_with_list_of_profiler_variables(list_of_added_variables):
    f = open("profiler_vars.txt", "w")
    for entry in list_of_added_variables:
        f.write(entry + "\n")


if __name__ == '__main__':

    args = parse_cmdline_arguments()

    if len(args.files) == 0:
        print("No files provided.")
        exit(0)

    # Generate exclude functions list if any file was passed
    exclude_functions_list = []
    if args.exclude_functions_file != None:
        with open(args.exclude_functions_file) as f:
            exclude_functions_list = f.readlines()
            exclude_functions_list = [string.strip() for string in exclude_functions_list if string.strip()] # remove newlines and whitespaces strings

    # Generate include functions list if any file was passed
    include_functions_list = []
    if args.include_functions_file != None:
        with open(args.include_functions_file) as f:
            include_functions_list = f.readlines()
            include_functions_list = [string.strip() for string in include_functions_list if string.strip()] # remove newlines and whitespaces strings

    global_functions_variables = []

    list_of_input_files = []
    for f in args.files:
        fs = f.replace("\n", " ")
        list_of_input_files.extend(fs.split(" "))

    for infile in list_of_input_files:
        global_functions_variables.extend(add_profiling_code_to_source_file(
            infile, args.count_only, exclude_functions_list, include_functions_list))

    create_profiler_source_and_header_files(global_functions_variables, args.count_only)
    create_file_with_list_of_profiler_variables(global_functions_variables)
    