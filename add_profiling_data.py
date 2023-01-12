#!/usr/bin/python
import sys
import re

def add_profiling_info_to_file(filename):
    with open(filename, "r", encoding='unicode_escape') as infile, open(filename + ".stub", "w") as outfile:
        cnt  = 0
        lines = []
        func_name = ""
        func_start = ""
        func_end = ""
        added_variables = []

        for line in infile:

            lines.append(line)        

            if "@{" in line or "@}" in line:
                if cnt == 0:
                    outfile.write(line)
                continue
        
            if "{" in line and "}" in line: # case when "{}"
                if cnt == 0:
                    outfile.write(line)
                continue

            if "{" in line:

                for rev_line in reversed(lines):
                    match = re.search(r"\s(\w+)[(]", rev_line)
                    if match:
                        func_name  = match.group(1)
                        ifnm = filename.replace(".", "_")
                        var_start  = ifnm + "_" + func_name + "_start"
                        var_diff   = ifnm + "_" + func_name + "_diff"
                        var_max    = ifnm + "_" + func_name + "_max"
                        var_cnt    = ifnm + "_" + func_name + "_cnt"
                        added_variables.append(var_start)
                        added_variables.append(var_diff)
                        added_variables.append(var_max)
                        added_variables.append(var_cnt)
                        func_start = "    " + var_start + " = GET_SYS_TICK_US();\n\n"
                        func_end   = "\n    " + var_diff + " = GET_ELAPSED_TIME_US(" + var_start + ");\n" \
                            "    if (" + var_diff + " > " + var_max + ") "  + var_max + " = " + var_diff + ";\n" \
                            "    " + var_cnt  + "++;\n"
                        break

                cnt += 1
                if cnt == 1:
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

        return added_variables


if __name__ == '__main__':   

    command_line_args = sys.argv
    if not sys.stdin.isatty():
        command_line_args.extend(sys.stdin.readlines())

    if command_line_args == 1:
        exit(0)

    global_functions_variables = []

    for arg_file in command_line_args:
        global_functions_variables.extend(add_profiling_info_to_file(arg_file))
    