#!/bin/bash

# echo every line and expand variables and prints a little + sign before the line
set -x

# specify build type
build_type=Debug

# get current working directory
script_dir=$(pwd | awk -F / '{print $NF}')

# put genarated files to separate directory
output_dir=output
mkdir -p $output_dir

# file where all files to be processed will be listed
list_of_files_file=$output_dir/file_list.txt

# Source file where all objects files are listed
objects_list=../STM32G0B1RE_PMCU/$build_type/objects.list

# If no arguments are passed then files will be generated form objects_list
# otherwise the command line arguments will be used as files to be used
if [ $# -eq 0 ]
then
    # No arguments supplied

    # generate/create a file with all the source filenames    
    cp $objects_list $list_of_files_file
    # transform file
    sed -i 's/^././' $list_of_files_file # replace first character with '.'
    sed -i 's/.\{2\}$/c/' $list_of_files_file # replace last 2 characters with 'c'
    sed -i '/Common\/profiler.c/d' $list_of_files_file # remove potential profiler.c to not profile the profiler
    sed -i 's/\/Core\/Src\//\/STM32G0B1RE_PMCU\/Core\/Src\//' $list_of_files_file # Replace core directory with the full path
    # remove files that we are not interested in
    sed -i '/\/Startup\//d' $list_of_files_file # remove startup files which in the case of this writting is assembly
    sed -i '/STM32G0xx_HAL_Driver/d' $list_of_files_file # Replace Drivers directory with the full path
    sed -i '/Middlewares/d' $list_of_files_file # Replace Drivers directory with the full path

    # split the files in that list into segments
    num_of_segments=1
    
else
    num_of_segments=1
    echo -e "$@" | tr ' ' '\n' > $list_of_files_file
fi

# Calculate chunk size
lines=$(wc -l < $list_of_files_file)
chunk_size=$(((lines+$num_of_segments-1)/$num_of_segments))

# Generate file_lists
for i in $(seq 1 $num_of_segments); do
    start=$(((i-1)*chunk_size+1))
    end=$(($i*chunk_size))
    sed -n "${start},${end}p" $list_of_files_file > "${output_dir}/file_list_${i}.txt"
done

# loop
for i in $(seq 1 $num_of_segments); do
    current_file=$output_dir/file_list_$i.txt
    echo "Processing $current_file"

    # git stage current dir and everything in it (output_dir - so we keep the generated data during loop runs)
    git add .    

    # discard unstaged git changes (to put the project back to base state):
    git submodule foreach --quiet --recursive git restore . --quiet
    git restore ..
    git clean -df

    # run the "add profiler code" script on files from script
    cat $current_file | xargs echo | python add_profiler_code.py
    mv profiler.c profiler.h ../Common
    # add pofiler.c to sources list so that make will build it
    grep -q "./Common/profiler.o" $objects_list
    if [ $? -eq 1 ]; then
        echo "\"./Common/profiler.o\"" >> $objects_list
    fi

    # rename the outputed profiler_vars.txt to something so we later know in what order were they (e.g. profiler_vars_1.txt)
    mv "profiler_vars.txt" "${output_dir}/profiler_vars_${i}.txt"

    # build project
    export PATH=$PATH:/c/ST/STM32CubeIDE_1.10.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.10.3-2021.10.win32_1.0.0.202111181127/tools/bin
    cd ../STM32G0B1RE_PMCU/$build_type/
    make -j 8 all

    # program mcu
    export PATH=$PATH:/c/Program\ Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/
    cd -
    merged_hex=$(find ../output/ -type f -name '*.hex' -mmin -2 -printf '%T@ %p\n' | sort -n | tail -1 | cut -f2- -d" ")
    STM32_Programmer_CLI.exe -c port=SWD -e all
    STM32_Programmer_CLI.exe -c port=SWD -w $merged_hex -v
    STM32_Programmer_CLI.exe -c port=SWD -rst
    #STM32_Programmer_CLI.exe -c SWD -run

    # start serial capture script and kill it after some time
    #timeout 65s python serial_to_file.py COM4 1000000
    timeout 75s python serial_to_file.py /dev/ttyS3 1000000

    # rename saved data
    mv "serial_data.txt" "${output_dir}/serial_data_${i}.txt"

done

# remove profiler.o from objects.list
# do we actually need this, I don't think so but I'm still keeping it here
sed -i '/profiler.o/d' $objects_list

# merge created files together
cat $(ls $output_dir/profiler_vars_*.txt | sort -V) > $output_dir/profiler_vars_all.txt
cat $(ls $output_dir/serial_data_*.txt | sort -V) > $output_dir/serial_data_all.txt

# turn of echo every line
set +x
