# Use this to capture information...

#create a function that records the number of stats and report average
#ideally writing small takes is taxing task. 
#So also create a script to record report and write stats when needed... 

import json
import csv
from concurrent.futures import ThreadPoolExecutor
import threading
import os

class event_recorder:
    def __init__(self):
        pass

class StatsRecorder:
    def __init__(self, filename, total_stats_filename,output_folder,max_records=1000):
        self.filename = os.path.join(output_folder, filename)
        #self.recorded_stats = []
        self.max_records = max_records  # Adjust this to your desired batch size
        self.total_stats_filename = os.path.join(output_folder, total_stats_filename)
        #self.filename = filename
        #self.recorded_stats = []
        #self.max_records = max_records  # Adjust this to your desired batch size
        #self.total_stats_filename = total_stats_filename
        self.recorded_stats = []
        self.total_stats = {}
        # Ensure the destination directory exists, create if not
        os.makedirs(output_folder, exist_ok=True)
        with open(self.filename, 'a+', newline='') as file:
            file.seek(0)
            if file.read(1) == '':
                writer = csv.writer(file)
                writer.writerow(["Instruction pointer", "Access type", "Address", "Id", "Time","RW"])
    
    def record_stats(self, ip, lc, address, id, time, rw):
        time=round(time,9)
        record = [ip, lc, hex(address), id, time,rw]
        self.recorded_stats.append(record)

        if len(self.recorded_stats) >= self.max_records:
            self.save_to_file()  # Write data to the file when a batch is reached

    def save_to_file(self):
        with open(self.filename, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(self.recorded_stats)
        self.recorded_stats.clear()  # Clear the recorded stats after saving    

    def update_total_stats(self, key):
        #for key, value in stats.items():
        #    self.total_stats[key] = self.total_stats.get(key, 0) + value
        self.total_stats[key]=self.total_stats.get(key,0)+ 1
    
    def sort_stats(self, data):
        return dict(sorted(data.items(), key=lambda item: (int(item[0][1:3]), item[0][3:], item[0][:2])))


    def save_total_stats(self):
        self.total_stats1=self.sort_stats(self.total_stats)
        with open(self.total_stats_filename, 'w') as file:
            json.dump(self.total_stats1, file, indent=4)