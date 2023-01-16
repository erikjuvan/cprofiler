#!/bin/bash

# generate/create a file with all the source filenames
list_of_files_filename="file_list.txt"

# split the files in that list into 10 segments/lists
file=$list_of_files_filename
lines=$(wc -l < $file)
chunk_size=$(((lines+9)/10))

# put genarated files to separate directory
prof_dir=prof_out
mkdir -p $prof_dir

for i in {1..10}; do
    start=$(((i-1)*chunk_size+1))
    end=$(($i*chunk_size))
    sed -n "${start},${end}p" $file > "${prof_dir}/file_list_${i}.txt"
done

# loop
for i in {1..10}; do
    current_file="${prof_dir}/file_list_${i}.txt"
    echo "Processing $current_file"
    # Do something with the current file here

    # git stage prof_dir
    git add $prof_dir

    # remove unstaged git changes (to put the project back to base state):
    git clean -df && git checkout -- .

    # run the "add profiler code" script on files from script
    cat current_file | xargs echo | python add_profiler_code.py

    # rename the outputed profiler_vars.txt to something so we later know in what order were they (e.g. profiler_vars_1.txt)
    mv "profiler_vars.txt" "${prof_dir}/profiler_vars_${i}.txt"

    # build project
    export PATH=$PATH:/c/ST/STM32CubeIDE_1.10.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.10.3-2021.10.win32_1.0.0.202111181127/tools/bin
    cd STM32G0B1RE_PMCU/Debug/
    make all

    # program mcu
    export PATH=$PATH:/c/Program\ Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/
    cd -
    find output/ -type f -name '*.hex' -mtime -1
    STM32_Programmer_CLI.exe -c SWD -e [all]
    STM32_Programmer_CLI.exe -c SWD -w STM32G0B1RE_PMCU_BOOTLOADER_SAFE_USER.hex 0x08000000 -v
    STM32_Programmer_CLI.exe -c SWD -rst
    STM32_Programmer_CLI.exe -c SWD -run

    # start serial capture script and kill it after some time
    timeout 2s python serial_to_file.py

    # rename saved data
    mv "serial_data.txt" "${prof_dir}/serial_data_${i}.txt"

done

# merge created files together
cat $(ls prof_out/profiler_vars_*.txt | sort -V) > prof_out/profiler_vars_all.txt
cat $(ls prof_out/serial_data_*.txt | sort -V) > prof_out/serial_data_all.txt
