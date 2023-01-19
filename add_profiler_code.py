#!/usr/bin/python
import sys
import re
import os

variable_counter = 1

def add_profiling_info_to_file(filename):
    global variable_counter
    infilename = filename
    outfilename = filename + ".profiled"

    print(filename)

    #with open(filename, "r", encoding='unicode_escape') as infile, open(outfilename, "w") as outfile:
    with open(filename, "r") as infile, open(outfilename, "w") as outfile:
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

        outfile.write("#include \"profiler.h\"\n\n")

        lines_history = []
        write_func_end_to_outfile = False
        for line in infile:

            lines_history.append(line)

            # check if the line is a comment "//"
            match = re.search(r"^\s*\/\/", line)
            if match:
                outfile.write(line)
                continue

            if "@{" in line or "@}" in line:
                outfile.write(line)
                continue
        
            # case when "{}"
            if "{" in line and "}" in line:
                outfile.write(line)
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
                        def make_var(name):
                            var_name = "_" + str(variable_counter) + "_" + infilename + "_" + func_name + name
                            added_variables.append(var_name)
                            return var_name
                        var_cnt = make_var("_cnt")
                        var_accum = make_var("_accum")

                        variable_counter += 1

                        func_start = """
    /// PROFILER ///
    uint16_t _profiler_start = PROFILER_GET_US();
    ////////////////\n"""

                        func_end = """
    /// PROFILER ///
    if (profiler_running)
    {{
        profiler_vars.{vc}++;
        profiler_vars.{vacc} += PROFILER_GET_ELAPSED_US(_profiler_start);
    }}
    ////////////////\n""".format(vc = var_cnt, vacc = var_accum)

                        outfile.write(line)
                        outfile.write(func_start)
                        write_func_end_to_outfile = True
                        continue

            if "}" in line:
                cnt -= 1
                if cnt == 0 and write_func_end_to_outfile == True:
                    outfile.write(func_end)
                    outfile.write(line)
                    write_func_end_to_outfile = False
                    continue

            outfile.write(line)

        outfile.close()
        os.replace(outfilename, filename)

        return added_variables


def add_profiler_variables_to_new_file(list_of_added_variables):
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
{
    uint32_t v[2]; // value
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
        IWDG->KR = 0x0000AAAAu;
        printf("%ld,%ld,", p->v[0], p->v[1]);
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
        printf("\\n%ld Profiler start %c\\n", PROFILER_GET_MS(), marker);
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
        printf("\\n%ld Profiler stop %c\\n", PROFILER_GET_MS(), marker);
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

#define PROFILER_GET_US() TIM7->CNT
#define PROFILER_GET_ELAPSED_US(start) ((uint16_t)PROFILER_GET_US() - (uint16_t)start)

#define PROFILER_GET_MS() TIM2->CNT
#define PROFILER_GET_ELAPSED_MS(start) ((uint32_t)PROFILER_GET_MS() - (uint32_t)start)

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

def generate_list_of_profiler_variables(list_of_added_variables):
    f = open("profiler_vars.txt", "w")
    for entry in list_of_added_variables:
        f.write(entry + "\n")


if __name__ == '__main__':   

    command_line_args = sys.argv
    if not sys.stdin.isatty():
        command_line_args.extend(sys.stdin.readlines())

    command_line_args.pop(0)

    if len(command_line_args) == 0:
        exit(0)

    list_of_input_files = command_line_args[0].replace("\n", "")
    list_of_input_files = list_of_input_files.split(" ")

    global_functions_variables = []

    for arg_file in list_of_input_files:
        global_functions_variables.extend(add_profiling_info_to_file(arg_file))

    add_profiler_variables_to_new_file(global_functions_variables)
    generate_list_of_profiler_variables(global_functions_variables)
    