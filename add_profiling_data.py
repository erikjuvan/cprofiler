#!/usr/bin/python
import sys
import re
import os

def add_profiling_info_to_file(filename):
    infilename = filename
    outfilename = filename + ".profiled"

    with open(filename, "r", encoding='unicode_escape') as infile, open(outfilename, "w") as outfile:
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

        prev_line = ""
        for line in infile:

            if "@{" in line or "@}" in line:
                if cnt == 0:
                    outfile.write(line)
                continue
        
            if "{" in line and "}" in line: # case when "{}"
                if cnt == 0:
                    outfile.write(line)
                continue

            if "{" in line:
                cnt += 1
                if cnt == 1:
                    match = re.search(r"\s(\w+)[(]", prev_line)
                    if match:
                        func_name  = match.group(1)                        
                        var_start  = infilename + "_" + func_name + "_start"
                        var_diff   = infilename + "_" + func_name + "_diff"
                        var_max    = infilename + "_" + func_name + "_max"
                        var_cnt    = infilename + "_" + func_name + "_cnt"
                        added_variables.append(var_start)
                        added_variables.append(var_diff)
                        added_variables.append(var_max)
                        added_variables.append(var_cnt)

                        func_start = """    if (profiler_recording)
    {{
        profiler_vars.{vs} = GET_SYS_TICK_US();
    }}\n\n""".format(vs = var_start)

                        func_end   = """    if (profiler_recording)
    {{
        profiler_vars.{vd} = GET_ELAPSED_TIME_US(profiler_vars.{vs});
        if (profiler_vars.{vd} > profiler_vars.{vm}) profiler_vars.{vm} = profiler_vars.{vd};
        profiler_vars.{vc}++;
    }}\n""".format(vd = var_diff, vs = var_start, vm = var_max, vc = var_cnt)


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

            prev_line = line
        
        outfile.close()
        os.replace(outfilename, filename)

        return added_variables


def add_profiler_variables_to_new_file(list_of_added_variables):
    f = open("profiler.c", "w")

    profiler_src = """#include <stdint.h>
#include "trace.h"

int profiler_recording = 1;

struct
{
"""

    for entry in list_of_added_variables:
        profiler_src += "    uint32_t " + entry + " = 0;\n"

    profiler_src += "} profiler_vars;\n\n"

    profiler_src += """

static void profiler_print_vars(void)
{    
    uint32_t *p = (uint32_t *)&profiler_vars;
    for (int i = 0; i < sizeof(profiler_vars / sizeof(uint32_t)); ++i, p++)
    {
        printf("%ld\\n", *p);
    }
}

void profiler_run(void)
{
    static uint32_t start = 0;

    if (GET_ELAPSED_TIME_MS(start) > 1000)
    {
        start = GET_SYS_TICK_MS()
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
"""

    f.write(profiler_src)


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
    