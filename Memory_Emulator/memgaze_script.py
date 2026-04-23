import os
import datetime
import shutil
import time
import subprocess
import sys
import fnmatch

def copy_directory_contents(source_dir, destination_dir):
    # Ensure the destination directory exists
    os.makedirs(destination_dir, exist_ok=True)

    # Copy each item from source to destination
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        destination_item = os.path.join(destination_dir, item)

        if os.path.isdir(source_item):
            # Recursively copy directories
            shutil.copytree(source_item, destination_item, dirs_exist_ok=True)
        else:
            # Copy files
            shutil.copy2(source_item, destination_item)


def get_target_process_pid(app_name):
    """
    Attempt to find the PID of the target process by its name.
    Ensures robustness in case no matching process is found or multiple processes exist.
    """
    try:
        # Use subprocess to call pgrep and fetch the PID list
        print(f"App Name : {app_name}")
        pid_list = subprocess.check_output(["pgrep", "-x", app_name]).decode().strip().split()
        
        # If no PIDs were found (safety check, though subprocess should already handle errors)
        if not pid_list:
            print(f"No process found with name: {app_name}")
            return None
        
        # If multiple PIDs are returned, handle them accordingly
        if len(pid_list) > 1:
            print(f"Multiple processes found for '{app_name}': {pid_list}")
            return pid_list  # Return all PIDs as a list
        
        # Single PID case
        return int(pid_list[0])
    
    except subprocess.CalledProcessError:
        # Handle error for 'pgrep' (e.g., no process found)
        print(f"No process found with name: {app_name}")
        return None
    except ValueError as ve:
        # Handle any unexpected value decoding issues
        print(f"Error decoding PID: {str(ve)}")
        return None

def get_target_process_pid2(app_name):
    """
    Attempt to find the PID of the target process launched by memgaze-run.
    This function needs to be adapted based on how you can best identify the process.
    """
    # Example using pgrep - this is a simplistic approach and might need refinement
    max_length = 15
    if len(app_name) > max_length:
        app_name=app_name[:max_length]
        print(app_name)
    try:
        pid = subprocess.check_output(["pgrep", "-x", app_name]).decode().strip()
        return pid
    except subprocess.CalledProcessError:
        return None

def run_and_monitor(app, buff, per, args):
    # Assuming the target application is identifiable by a unique name pattern
    app_name_pattern = f"{app}-memgaze"

    destination=f"{app}_ls_b{buff}_p{per}"
    print("From to : ",os.getcwd() , destination)
    os.chdir(destination)
    cmd=f"{memgaze_dir}/memgaze-run -p {per} -b {buff} -e pt-load-store {memgaze_dir}/{destination}/{app_name_pattern} {args}"
    cmd_parts = cmd.split()   
        
    # Start memgaze-run
    process=subprocess.Popen(cmd_parts)
    print("memgaze-run started, waiting for target process to launch...")

    # Wait a moment to ensure the target process has started
    max_attempts = 10
    found_pid = False
    target_pid = None

    for attempt in range(max_attempts):
        time.sleep(0.5)  # Wait a bit before each PID check to give the process time to start
        target_pid = get_target_process_pid(app_name_pattern)
        if target_pid:
            found_pid = True
            break  # Exit the loop if PID is found
        else:
            print(f"Attempt {attempt + 1} failed to find target process PID.")

    if not found_pid:
        print("Failed to find target process PID after 10 attempts. Exiting the capture map capture program")
        return

    print(f"Target process PID for {app_name_pattern}: {target_pid}")

    output_file = f"{memgaze_dir}/{app}_ls_b{buff}_p{per}/pagemap_info_{app}_{target_pid}"
    monitor_cmd = ["sudo", f"{memgaze_dir}/pagemap_smap_monitor", str(target_pid), output_file]
    process2=subprocess.Popen(monitor_cmd)
    print(f"Monitoring started for PID : {target_pid}")

    # Additional logic to wait for the target process to finish and to check capture success...
    process.wait()
    print(f"Program {target_pid} has finished execution.")
    print("Current PWD : {} Changing into Dir : {}", os.getcwd(), memgaze_dir)
    os.chdir(memgaze_dir)


# Get today's date
today = datetime.date.today()

# Ask user for name of result directory
#result_dir_name = input("Enter name of result directory: ")
result_path="/home/memgaze-ori/home_output"
exp_info="spec_apps"
# Create directory with today's date and user-specified name
directory_name = "{}/{}_{}".format(result_path,today.strftime("%Y-%m-%d"),exp_info)
if not os.path.exists(directory_name):
    os.makedirs(directory_name)

applications={
    "bc": ["/home/gapbs",f"-g 18"],
    }

memgaze_dir="/home/memgaze-ori/install/bin"
buffer_size=["8193"]
num_runs=1
period=["0"]
NUM_THREADS='4'
timing_info=[]
spec_flag=1 # or 1. If 1 move the base fodler contents in memgaze_inst folder
#for app in applications:
for app, (path, args) in applications.items():
	for per in period:
		for buff in buffer_size:
			for run in range(num_runs):
				new_dir_name="{}/run_{}".format(directory_name,run)
				if not os.path.exists(new_dir_name):
					os.makedirs(new_dir_name)
				os.environ['OMP_PROC_BIND'] = "close"
				os.environ['OMP_PLACES'] = "{0:1}:8:2"
				os.environ['OMP_NUM_THREADS'] = NUM_THREADS
				print("OMP_PROC_BIND is set to:", os.environ.get('OMP_PROC_BIND'))
				print("OMP_PLACES is set to:", os.environ.get('OMP_PLACES'))
				print("OMP_NUM_THREADS is set to:", os.environ.get('OMP_NUM_THREADS'))
				print(app,path,args)
				cmd="./memgaze-inst -o {}_ls_b{}_p{} -s 1 -f 1 {}/{}".format(app,buff,per,path,app)
				print(cmd)
				start_time=time.time()
				os.system(cmd)
				end_time=time.time()
				time_inst=end_time-start_time
				if(spec_flag):
					destination="{}_ls_b{}_p{}".format(app,buff,per)
					copy_directory_contents(path,destination)
				#cmd="./memgaze-run -p {} -b {} -e pt-load-store {}_ls_b{}_p{}/{}-memgaze -g {}".format(per,buff,app,buff,per,app,runtime)
				start_time=time.time()
				#os.system(cmd)
				run_and_monitor(app,buff,per,args)
				end_time=time.time()
				time_run=end_time-start_time
				os.chdir(memgaze_dir)
				cmd="./memgaze-xtrace {}/{}_ls_b{}_p{}/{}-memgaze-trace-b{}-p{}/".format(memgaze_dir,app,buff,per,app,buff,per)
				start_time=time.time()
				os.system(cmd)
				end_time=time.time()
				time_xtrace=end_time-start_time

				timing_string="The inst, run and xtrace timing information for {}_{}:{};{};{}".format(app,run,time_inst,time_run,time_xtrace)
				timing_info.append(timing_string)
				#filename=
				shutil.move("{}/{}_ls_b{}_p{}/{}-memgaze-trace-b{}-p{}".format(memgaze_dir,app,buff,per,app,buff,per), new_dir_name)
				shutil.move("{}_ls_b{}_p{}".format(app,buff,per), new_dir_name)


with open(f"{directory_name}/elapsed_times.txt", "w") as file:
    print("Elapsed times:")
    for i in timing_info:
        print(f" {i} ")
        file.write(f" {i}\n")

