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
                        var_avg = make_var("_avg")
                        var_avg_last_16 = make_var("_avg_last_16")                        
                        var_max = make_var("_max")
                        var_dur_us = make_var("_dur_us")
                        var_accum = make_var("_accum")
                        var_accum_last_16 = make_var("_accum_last_16")
                        variable_counter += 1

                        func_start = """    /// PROFILER ///
    static uint32_t _profiler_start = 0;
    if (profiler_recording)
    {        
        _profiler_start = GET_SYS_TICK_US();
    }
    ////////////////
    \n"""

                        func_end = """
    /// PROFILER ///
    if (profiler_recording)
    {{
        profiler_vars.{vd} = GET_ELAPSED_TIME_US(_profiler_start);
        profiler_vars.{vc}++;
        profiler_vars.{vacc} += profiler_vars.{vd};
        profiler_vars.{vaccl16} += profiler_vars.{vd};
        if (profiler_vars.{vd} > profiler_vars.{vm}) profiler_vars.{vm} = profiler_vars.{vd};
        if ((profiler_vars.{vc} & 0xF) == 0)
        {{
            profiler_vars.{vavgl16} = profiler_vars.{vaccl16} >> 4;
            profiler_vars.{vaccl16} = 0;
        }}
    }}
    ////////////////\n""".format(vd = var_dur_us, vc = var_cnt, vacc = var_accum, vaccl16 = var_accum_last_16, vavgl16 = var_avg_last_16, vm = var_max)

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
#include "trace.h"
#include "profiler.h"

int profiler_recording = 1;

struct profiler_vars profiler_vars = {0};

static uint32_t _profiler_running = 0;
static uint32_t _profiler_start_ts = 0;
static uint32_t _profiler_print_cnt = 0;

typedef struct
{
    uint32_t v[7]; // value
} prof_func_data;

static void profiler_print_vars(void)
{    
    printf("=====BEGIN %ld\\n", _profiler_print_cnt);
    int size = sizeof(profiler_vars) / sizeof(prof_func_data);
    prof_func_data *p = (prof_func_data *)&profiler_vars;
    for (int i = 0; i < size; ++i, ++p)
    {
        WWDG->CR = 127;
        IWDG->KR = 0x0000AAAAu;
        p->v[1] = p->v[5] / p->v[0]; // calculate total average
        printf("%ld,%ld,%ld,%ld,%ld,%ld,%ld,", 
            p->v[0], p->v[1], p->v[2], p->v[3], p->v[4], p->v[5], p->v[6]);
    }
    printf("\\n=====END %ld\\n", _profiler_print_cnt);
    _profiler_print_cnt++;
}

void profiler_run(void)
{
    if (!_profiler_running)
        return;

    if (GET_ELAPSED_TIME_MS(_profiler_start_ts) > 60000)
    {
        _profiler_start_ts = GET_SYS_TICK_MS();
        if (profiler_recording == 1)
        {
            profiler_recording = 0;
            profiler_print_vars();
        }
        else
        {
            profiler_recording = 1;
        }
    }
}

void profiler_init(void)
{
    printf("--------------------\\nPROFILER INIT\\n%ld\\n--------------------\\n",
        GET_SYS_TICK_MS());

    _profiler_print_cnt = 0;
}

void profiler_start(void)
{
    printf("--------------------\\nPROFILER START\\n%ld\\n--------------------\\n",
        GET_SYS_TICK_MS());

    _profiler_start_ts = GET_SYS_TICK_MS();
    _profiler_running = 1;    
}

void profiler_stop(void)
{    
    _profiler_running = 0;
    printf("--------------------\\nPROFILER STOP\\n%ld\\n--------------------\\n",
        GET_SYS_TICK_MS());
}

"""

    fprofiler_c.write(profiler_c_src)


    fprofiler_h = open("profiler.h", "w")    

    profiler_h_src = """#pragma once

#include <stdint.h>
#include "app_macros.h"

struct profiler_vars
{
"""

    for entry in list_of_added_variables:
        profiler_h_src += "    uint32_t " + entry + ";\n"

    profiler_h_src += "} profiler_vars;\n\n"

    profiler_h_src += """
extern int profiler_recording;
extern struct profiler_vars profiler_vars;

void profiler_run(void);
void profiler_init(void);
void profiler_start(void);
void profiler_stop(void);

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
    