#!/usr/bin/bash

RED="31"
GREEN="32"
BOLDGREEN="\e[1;${GREEN}m"
ITALICRED="\e[3;${RED}m"
ENDCOLOR="\e[0m"


check_sudo_nopasswd() {
    # Check if sudo can be used without a password
    if sudo -n true 2>/dev/null; then
        echo -e "${BOLDGREEN} You can use sudo without a password.${ENDCOLOR}"
        return 0
    else
        echo "${ITALICRED} Error: Cannot use sudo without a password. Needed for HOME${ENDCOLOR}"
        echo "${ITALICRED} Exiting ${ENDCOLOR}"
        exit 1
    fi
}

#####################################################
##### Make sure sudo can be excecute ################
#####################################################

check_sudo_nopasswd

#####################################################
##### Change to install/bin dir ####################
#####################################################

cd install/bin/

echo -e "${BOLDGREEN}Changed to /home/memgaze-ori/install/bin/ ${ENDCOLOR}"

#####################################################
##### Run memgaze_script ###############################
#####################################################

echo -e "${BOLDGREEN} Running MEMGAZE${ENDCOLOR}"

echo -e "${BOLDGREEN} Output folder path : ${ENDCOLOR}"
sed -n 125p memgaze_script.py

Trace_output_folder=$(sed -n 125p memgaze_script.py)
#cleaned_Trace_output_folder="${Trace_output_folder#*\"}"
cleaned_Trace_output_folder=$(echo "$Trace_output_folder" | awk -F\" '{print $2}')

echo -e "${BOLDGREEN} Application parameters : ${ENDCOLOR}"
sed -n 133p memgaze_script.py

echo -e "${BOLDGREEN} MemGaze executables folder : ${ENDCOLOR}"
sed -n 136p memgaze_script.py

# Check if the path is valid and exists
if [ -d "$cleaned_Trace_output_folder" ]; then
    echo "Deleting contents inside memgaze output : $cleaned_Trace_output_folder"
    #rm -rf "$cleaned_Trace_output_folder"/*
    #echo "Contents deleted successfully."
else
    echo "Error: $cleaned_Trace_output_folder is not a valid directory."
fi

python3 memgaze_script.py

#####################################################
##### Run miss_ratres.py ############################
#####################################################

cd ../../

echo -e "${BOLDGREEN} Running miss_rates.py ${ENDCOLOR}"

echo -e "${BOLDGREEN} Output folder path : ${ENDCOLOR}"
sed -n 311p miss_rates.py

home_output=$(sed -n 311p miss_rates.py)
cleaned_home_output=$(echo "$home_output" | awk -F\" '{print $2}')

echo -e "Cleaned HOME output = $cleaned_home_output"

# Check if the path is valid and exists
if [ -d "$cleaned_home_output" ]; then
    echo "Deleting contents inside home output : $cleaned_home_output"
    #rm -rf "$cleaned_home_output"/*
    #echo "Contents deleted successfully."
else
    echo "Error: $cleaned_home_output is not a valid directory."
fi

echo -e "${BOLDGREEN} Input folder path : ${ENDCOLOR}"
sed -n 313p miss_rates.py

echo -e "${BOLDGREEN} Source files path : ${ENDCOLOR}"
sed -n 312p miss_rates.py

python3 miss_rates.py

#####################################################
##### RUNNING MemSim_to_dram.py #######################
#####################################################


echo -e "${BOLDGREEN} Running MemSim_to_dram.py ${ENDCOLOR}"

echo -e "${BOLDGREEN} Output folder path : ${ENDCOLOR}"
sed -n 82p MemSim_to_dram.py

echo -e "${BOLDGREEN} Input folder path : ${ENDCOLOR}"
sed -n 81p MemSim_to_dram.py

python3 MemSim_to_dram.py

#####################################################
##### Clear existing test dirs ######################
#####################################################

# Some where in cleaned_home_output exist trace and binanalysis files. find them.

trace_full_path=$(find $cleaned_Trace_output_folder -type f -name "*.trace")
binanalysis_full_path=$(find $cleaned_Trace_output_folder -type f -name "*.binanlys.log")

echo "Trace file at : $trace_full_path"
echo "binanly.log file at : $binanalysis_full_path"

if [ -z "$trace_full_path" ] || [ -z "$binanalysis_full_path" ]; then
  echo "Error: either tracefile or binanlys.log are not found. Exiting script."
  exit 1
fi


#####################################################
################## Run MemSim  ######################
#####################################################

echo -e "${BOLDGREEN}Changed to $(pwd) ${ENDCOLOR}"

#Find dram_input.csv in cleaned_home_output
time_compressed_output=$(find $cleaned_home_output -type f -name "*dram_input.csv")
echo -e "Time compressed DRAM csv is at : $time_compressed_output"

# Run MemSim contention model
g++ scripts/MemSim.cpp -o MemSim && ./MemSim --output_folder "$cleaned_home_output" --input_file "$time_compressed_output"


#####################################################
######## Bandwidth Prediction  ######################
#####################################################

python3 scripts/predict_bandwidth.py


#####################################################
############### Hot Sequences  ######################
#####################################################


## Get Dyninst Mappings File for current trace
scripts/filter-dynist-mappings.sh $binanalysis_full_path "${cleaned_home_output}/mappings.txt"

## Convert existing .trace file to remapped .trace file
python3 scripts/map-memgaze-ips.py "${cleaned_home_output}/mappings.txt" $trace_full_path "${cleaned_home_output}/remapped-bc-memgaze.trace"

##Get Basicblocks.json
python3 scripts/process-binanlys-log.py $binanalysis_full_path > "${cleaned_home_output}/basicblocks.json" 

##Run cluster analysis
sh run-cluster-analys.sh $cleaned_home_output

##Include remmaped IP as column in HOME's DRAM trace file output.
python3 scripts/map-memgaze-ips-MemSim.py "${cleaned_home_output}/mappings.txt" "${cleaned_home_output}/out_queue_bc_0.csv" "${cleaned_home_output}/remapped_out_queue_bc_0.csv"

# create dir to dump per blk accessess
# Check if the directory exists
if [ ! -d "${cleaned_home_output}/perblk" ]; then
    # Create the directory if it doesn't exist
    mkdir -p "${cleaned_home_output}/perblk"
    echo "Directory '${cleaned_home_output}/perblk' created."
else
    echo "Directory '${cleaned_home_output}/perblk' already exists."
fi

## Get per block DRAM accesses
./dump-block-mapping "${cleaned_home_output}/remapped_out_queue_bc_0.csv" "${cleaned_home_output}/basicblocks.json" "${cleaned_home_output}/perblk"

##Get per cluster metrics
python3 scripts/normalize_access.py "${cleaned_home_output}/out-3/clusters_nodes.txt" "${cleaned_home_output}/out-3/block_freq_mapping.txt" "${cleaned_home_output}/perblk"

