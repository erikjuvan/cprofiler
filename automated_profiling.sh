#!/bin/bash

# scripts used by this bash script
add_profiler_code=`readlink -f add_profiler_code.py`
parse_profiler_data=`readlink -f parse_profiler_data.py`
serial_to_file=`readlink -f serial_to_file.py`

##################################
## Parse command line arguments ##
##################################
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    -p|--proj-dir)
      PROJ_DIR="$2"
      shift # past argument
      shift # past value
      ;;
    -b|--build-type)
      BUILD_TYPE="$2"
      shift # past argument
      shift # past value
      ;;
    -o|--output-dir)
      OUTPUT_DIR="$2"
      shift # past argument
      shift # past value
      ;;
    -i|--input-file) # filename where all source files are listed
      INPUT_FILE="$2"
      shift # past argument
      shift # past value
      ;;
    -f|--fragmentation) # number of fragments
      FRAGMENTATION_NUM="$2"
      shift # past argument
      shift # past value
      ;;
    --comma-decimal-separator) # use , as decimal separator insted of default .
      COMMA_DECIMAL_SEPARATOR=1
      shift # past argument
      ;;
    -h|--help) # filename where all source files are listed        
      echo "Usage: automated_profiling.sh [OPTIONS]

      OPTIONS:
      -p, --proj-dir DIR         root project directory
      -b, --build-type TYPE      e.g. Debug, Release, ...
      -o, --output-dir DIR       output directory where all results will be saved
      -i, --input-file FILE      filename whit the list of files to be profiled
      -f, --fragmentation NUM    fragment profiling to NUM steps (sub-divide file list to NUM of sub-lists)

      --comma-decimal-separator  use comma as decimal separator, and ; as the field separator
      -h, --help                 this text

      Example: automated_profiling.sh -p project_dir -b Debug -o output -i files.txt"
      exit 1
      ;;
    --default)
      DEFAULT=YES
      shift # past argument
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}" # restore positional parameters
##################################

# export tool path
export PATH=$PATH:/c/ST/STM32CubeIDE_1.10.1/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.10.3-2021.10.win32_1.0.0.202111181127/tools/bin
export PATH=$PATH:/c/Program\ Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/

# check if PROJ_DIR is not set
if [ -z ${PROJ_DIR+x} ]
then
    echo "No project directory specified!"
    exit 1
fi

# check if BUILD_TYPE is not set
if [ -z ${BUILD_TYPE+x} ]
then
    echo "No build type specified!"
    exit 1
fi

# check if FRAGMENTATION_NUM is not set
if [ -z ${FRAGMENTATION_NUM+x} ]
then
    # set fragmentation to default 1
    FRAGMENTATION_NUM=1
fi

# echo every line and expand variables and prints a little + sign before the line
#set -x

# find the build dir by searching for makefile
build_dir=`find $PROJ_DIR -type f -iname makefile | grep -i $BUILD_TYPE | xargs dirname`
if [ ! -d $build_dir ]
then
    echo "No $build_dir found!"
    exit 1
fi

# Source file where all object files are listed
list_of_source_files=$INPUT_FILE
if [ ! -e $list_of_source_files ]
then
    echo "No $list_of_source_files found!"
    exit 1
fi

# create output directory
mkdir -p $OUTPUT_DIR

# file where all files to be processed will be listed
cp $list_of_source_files $OUTPUT_DIR/list_of_source_files.txt

# number of separate runs/segments
num_of_segments=$FRAGMENTATION_NUM

# NOTE! profiler.c must exist in the project IDE and be build with it beforehand so the make system has it included
run_profiler () {
    current_file=$1
    echo "Processing $current_file"

    # discard unstaged git changes (to put the project back to base state):
    cd $PROJ_DIR
    git submodule foreach --quiet --recursive git restore . --quiet
    git restore .
    git clean -df
    cd -

    # run the "add profiler code" script on files from script
    cat $current_file | xargs echo | python add_profiler_code.py

    # check if script finished successfully
    if [ ! -e profiler.c ]
    then
        echo "Error executing script!"
        exit 1
    fi    
    # move profiler source files to project dir
    mv profiler.c profiler.h $PROJ_DIR
    # and move list of generated variables to output dir
    mv profiler_vars.txt $OUTPUT_DIR

    # build project (NOTE!!! Debug folder has to exist, meaning that we have tu run the build process in the IDE beforehand)
    cd $build_dir
    make -j 8 all
    cd -

    # program mcu    
    cd $PROJ_DIR
    merged_hex=$(find ../output/ -type f -name '*.hex' -mmin -2 -printf '%T@ %p\n' | sort -n | tail -1 | cut -f2- -d" ")
    # check if hex exists
    if [ ! -e $merged_hex ]
    then
        echo "No merged hex found!"
        exit 1
    fi   
    STM32_Programmer_CLI.exe -c port=SWD -e all
    STM32_Programmer_CLI.exe -c port=SWD -w $merged_hex -v
    STM32_Programmer_CLI.exe -c port=SWD -rst
    cd -

    # start serial capture script, it will terminate on its own
    python serial_to_file.py /dev/ttyS3 1000000

    # move saved data
    mv serial_data.txt $OUTPUT_DIR
}

if [ $num_of_segments -gt 1 ]
then
    # Calculate chunk size
    lines=$(wc -l < $list_of_source_files)
    chunk_size=$(((lines+$num_of_segments-1)/$num_of_segments))

    # Generate file_lists
    for i in $(seq 1 $num_of_segments); do
        start=$(((i-1)*chunk_size+1))
        end=$(($i*chunk_size))
        sed -n "${start},${end}p" $list_of_source_files > $OUTPUT_DIR/file_list_$i.txt
    done

    # loop
    for i in $(seq 1 $num_of_segments); do
        run_profiler $OUTPUT_DIR/file_list_$i.txt

        # rename file to something so we later know in what order were they (e.g. profiler_vars_1.txt, serial_data_1.txt)
        mv $OUTPUT_DIR/profiler_vars.txt $OUTPUT_DIR/profiler_vars_$i.txt
        mv $OUTPUT_DIR/serial_data.txt $OUTPUT_DIR/serial_data_$i.txt
    done

    # join all files together
    cat $OUTPUT_DIR/profiler_vars_$i.txt > $OUTPUT_DIR/profiler_vars.txt
    cat $OUTPUT_DIR/serial_data_$i.txt > $OUTPUT_DIR/serial_data.txt
else
    run_profiler $OUTPUT_DIR/list_of_source_files.txt
fi

# parse output
python $parse_profiler_data $OUTPUT_DIR/profiler_vars.txt $OUTPUT_DIR/serial_data.txt > $OUTPUT_DIR/parsed_data.txt

# convert to comma delimited separator if requested
if [ $COMMA_DECIMAL_SEPARATOR -eq 1 ]
then
    sed -i 's/,/;/g' $OUTPUT_DIR/parsed_data.txt
    sed -i 's/\./,/g' $OUTPUT_DIR/parsed_data.txt
fi

# turn of echo every line
set +x



#########################
## Useful but not used ##
#########################

# convert lines of files with partial or no path to lines with full path
: <<'END_COMMENT'
# python way
python << END
#!/bin/python

def find_files():
    import os

    # File containing file names
    file_names_file = $list_of_source_files

    # The directory where the files are located
    base_path = $PROJ_DIR

    # Read file names from the file
    with open(file_names_file, 'r') as f:
        file_names = f.read().splitlines()

    # Find the full path of all the files
    for dirpath, dirnames, filenames in os.walk(base_path):
        if ".git" in dirpath: # don't search in .git directory
            continue            
        #print("{p} {n} {f}".format(p=dirpath, n=dirnames, f=filenames))
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            for tgt in file_names:
                if tgt in file_path:
                    print(file_path)
END

# bash
# find in files.txt file on location
# (NOTE!!! on windows there is a hidden '\r' in xargs output so we must remove it otherwise it doesn't find any line containing a newline at the end)
# 1
xargs -a files.txt printf '%s\0' | tr -d $'\r' | xargs -0 -I {} find /c/Users/erikj/home/devel/work/pu/boot_safe_user/user/ -iwholename '*{}'
# 2
cat files.txt | while read in; do echo $in | tr -d '\r' | xargs -I {} find /c/Users/erikj/home/devel/work/pu/boot_safe_user/user/ -iwholename '*{}' ; done
END_COMMENT