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
    # profiler.c must exist in the objects_list file (build must be ran beforehand in the IDE with the profiler.c file in place)

    # rename the outputed profiler_vars.txt to something so we later know in what order were they (e.g. profiler_vars_1.txt)
    mv "profiler_vars.txt" "${output_dir}/profiler_vars_${i}.txt"

    # build project (NOTE!!! Debug folder has to exist, meaning that we have tu run the build process in the IDE beforehand)
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

    # start serial capture script, it will terminate on its own
    python serial_to_file.py /dev/ttyS3 1000000

    # rename saved data
    mv "serial_data.txt" "${output_dir}/serial_data_${i}.txt"

done

# merge created files together, but first check if file already exsists and add sequential number if it exsists
find_nonexsistent_filename() {
    if [[ -e $1.txt || -L $1.txt ]] ; then
        i=1
        while [[ -e $1_$i.txt || -L $1_$i.txt ]] ; do
            let i++
        done
        name=$1_$i
    fi
    echo $name.txt  
}

# merge created files together, but don't overwrite existing files but instead create a new one
# prof_vars_fname=$(find_nonexsistent_filename $output_dir/profiler_vars_all)
# ser_data_fname=$(find_nonexsistent_filename $output_dir/serial_data_all)
# cat $(ls $output_dir/profiler_vars_*.txt | sort -V) > $prof_vars_fname
# cat $(ls $output_dir/serial_data_*.txt | sort -V) > $ser_data_fname

# merge created files together
cat $(ls $output_dir/profiler_vars_*.txt | sort -V) > $output_dir/profiler_vars_all.txt
cat $(ls $output_dir/serial_data_*.txt | sort -V) > $output_dir/serial_data_all.txt

# turn of echo every line
set +x
