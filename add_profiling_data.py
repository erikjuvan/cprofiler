#!/usr/bin/python
import sys
import re
import os

def add_profiling_info_to_file(filename):
    infilename = filename
    outfilename = filename + ".profiled"

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

        lines = []
        for line in infile:

            lines.append(line)

            # check if the line is a comment "//"
            match = re.search(r"^\s*\/\/", line)
            if match:
                outfile.write(line)
                continue

            if "@{" in line or "@}" in line:
                outfile.write(line)
                continue
        
            if "{" in line and "}" in line: # case when "{}"
                outfile.write(line)
                continue

            if "{" in line:
                cnt += 1
                if cnt == 1:
                    match_found = False
                    prev_line_lookups = 0
                    for l in reversed(lines):

                        # remove any text following '{'
                        if "{" in l:
                            l = l[:l.index('{')]

                        # regex to find function name
                        match = re.search(r"\s(\w+)\([^(]*$", l)
                        if match:
                            if "sizeof" not in l: # if there is a match make sure it is not a sizeof function
                                match_found = True
                                break

                        # don't look more than 3 previous lines
                        prev_line_lookups += 1
                        if prev_line_lookups >= 3:
                            break

                    if match_found:
                        func_name = match.group(1)
                        def make_var(name):
                            var_name = infilename + "_" + func_name + name
                            added_variables.append(var_name)
                            return var_name
                        var_dur    = make_var("_dur")
                        var_accum  = make_var("_accum")
                        var_avg_accum = make_var("_avg_accum")
                        var_avg    = make_var("_avg")
                        var_max    = make_var("_max")
                        var_cnt    = make_var("_cnt")

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
        profiler_vars.{vavgacc} += profiler_vars.{vd};
        if (profiler_vars.{vd} > profiler_vars.{vm}) profiler_vars.{vm} = profiler_vars.{vd};
        if ((profiler_vars.{vc} & 0xF) == 0)
        {{
            profiler_vars.{vavg} = profiler_vars.{vavgacc} >> 4;
            profiler_vars.{vavgacc} = 0;
        }}
    }}
    ////////////////\n""".format(vd = var_dur, vacc = var_accum, vavgacc = var_avg_accum, vavg = var_avg, vm = var_max, vc = var_cnt)

                        outfile.write(line)
                        outfile.write(func_start)
                        continue

            if "}" in line:
                cnt -= 1
                if cnt == 0:
                    outfile.write(func_end)
                    outfile.write(line)
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

static int _profiler_running = 0;
static int _profiler_print_cnt = 0;

static void profiler_print_vars(void)
{    
    printf("=====BEGIN %d\\n", _profiler_print_cnt);
    uint32_t *p = (uint32_t *)&profiler_vars;    
    for (int i = 0; i < (sizeof(profiler_vars) / sizeof(uint32_t)); ++i, p++)
    {
        printf("%ld,", *p);
    }
    printf("\\n=====END %d\\n", _profiler_print_cnt);
    _profiler_print_cnt++;
}

void profiler_run(void)
{
    static uint32_t start = 0;

    if (!_profiler_running)
        return;

    if (GET_ELAPSED_TIME_MS(start) > 1000)
    {
        start = GET_SYS_TICK_MS();
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

    profiler_h_src = """
#pragma once

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
    