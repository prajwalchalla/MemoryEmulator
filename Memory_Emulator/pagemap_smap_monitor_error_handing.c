#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>
#include <sys/wait.h>

#define PAGE_SIZE 4096
#define PAGEMAP_ENTRY_SIZE 8
#define CHECK_INTERVAL 50 // Check interval in milliseconds
#define THRESHOLD 40 // Threshold for changes in RSS/PSS in kB


int is_pid_running(pid_t pid) {
    // The kill call with a signal of 0 performs an error check without sending a signal
    // - If kill returns 0, the process is still running
    // - If kill returns -1 and errno is set to ESRCH, no process matches the specified PID
    if (kill(pid, 0) == 0) {
        return 1; // Process exists
    } else {
        if (errno == ESRCH) {
            return 0; // Process does not exist
        }
        // In case of other errors, assume process exists
        return 1;
    }
}


// Function to print a physical address for a given virtual address
// Returns 0 on success, -1 on error
/*int print_physical_address(FILE* output_fp, int pagemap_fd, uint64_t vaddr) {
    uint64_t value;
    off_t offset = (vaddr / PAGE_SIZE) * PAGEMAP_ENTRY_SIZE;
    ssize_t read_bytes = pread(pagemap_fd, &value, PAGEMAP_ENTRY_SIZE, offset);

    if (read_bytes != PAGEMAP_ENTRY_SIZE) {
        perror("Failed to read pagemap entry");
        return -1; // Signal read failure
    }

    if (value & (1ULL << 63)) { // Page present check
        uint64_t pfn = value & 0x7FFFFFFFFFFFFF;
        uint64_t physical_address = pfn * PAGE_SIZE;
        fprintf(output_fp, "0x%016llx 0x%016llx\n", (unsigned long long)vaddr, (unsigned long long)physical_address);
    }
    return 0;
}*/


int print_physical_address(FILE* output_fp, int pagemap_fd, uint64_t vaddr) {
    uint64_t value;
    off_t offset = (vaddr / PAGE_SIZE) * PAGEMAP_ENTRY_SIZE;
    ssize_t read_bytes;

    read_bytes = pread(pagemap_fd, &value, PAGEMAP_ENTRY_SIZE, offset);
    if (read_bytes == -1) {
        //perror("Failed to read pagemap entry");  // Detailed error message
        fprintf(stderr, "Failed to read pagemap entry: %s\n", strerror(errno));
        fprintf(output_fp, "Failed to read pagemap entry: %s\n", strerror(errno));
        return -1; // Signal read failure only if pread truly fails
    } else if (read_bytes != PAGEMAP_ENTRY_SIZE) {
        // Handling case where read bytes do not match expected, but is not an I/O error
        fprintf(stderr, "Incomplete read: Expected %d, got %zd bytes\n", PAGEMAP_ENTRY_SIZE, read_bytes);
        fprintf(output_fp, "Incomplete read: Expected %d, got %zd bytes at address 0x%llx\n", PAGEMAP_ENTRY_SIZE, read_bytes, (unsigned long long)vaddr);
        if ((vaddr & 0xFF00000000000000) == 0xFF00000000000000) {
            return 0; // Indicate no hard error for kernel space or special mappings
        } 
        else {
            
            return 1; // Indicate read issue for addresses not starting with 0xff
        }
    }

    // Check the "page present" bit to see if the page is actually present
    if (value & (1ULL << 63)) { 
        uint64_t pfn = value & 0x7FFFFFFFFFFFFF;
        uint64_t physical_address = pfn * PAGE_SIZE;
        fprintf(output_fp, "0x%016llx 0x%016llx\n", (unsigned long long)vaddr, (unsigned long long)physical_address);
    }
    return 0;
}

// Function to handle reading of virtual to physical address mappings
// Returns 0 on success, non-zero on failure
int process_pid(pid_t pid, const char* output_file) {
    char maps_path[256], pagemap_path[256];
    snprintf(maps_path, sizeof(maps_path), "/proc/%d/maps", pid);
    snprintf(pagemap_path, sizeof(pagemap_path), "/proc/%d/pagemap", pid);
    FILE *maps_file = fopen(maps_path, "r");
    if (!maps_file) {
        perror("Error opening maps file");
        return 1;
    }
    FILE* output_fp = fopen(output_file, "w");
    if (!output_fp) {
        perror("Error opening output file");
        fclose(maps_file);
        return 1;
    }
    int pagemap_fd = open(pagemap_path, O_RDONLY);
    if (pagemap_fd < 0) {
        perror("Error opening pagemap file");
        fclose(maps_file);
        fclose(output_fp);
        return 1;
    }
    char line[1024];
    int error_occurred = 0;
    while (fgets(line, sizeof(line), maps_file)) {
        uint64_t start_vaddr, end_vaddr;
        if (sscanf(line, "%lx-%lx", &start_vaddr, &end_vaddr) == 2) {
            for (uint64_t vaddr = start_vaddr; vaddr < end_vaddr; vaddr += PAGE_SIZE) {
                if (print_physical_address(output_fp, pagemap_fd, vaddr) != 0) {
                    error_occurred = 1;
                    break;
                }
            }
            if (error_occurred) break;
        }
    }
    fclose(maps_file);
    fclose(output_fp);
    close(pagemap_fd);
    return error_occurred ? 1 : 0;
}

// Monitor function to continuously check and respond to memory usage changes
void monitor_and_capture(pid_t pid, const char* base_output_file) {
    char smaps_rollup_path[256];
    snprintf(smaps_rollup_path, sizeof(smaps_rollup_path), "/proc/%d/smaps_rollup", pid);

    unsigned long prev_rss = 0, prev_pss = 0, prev_swap_pss = 0;
    int file_suffix = 0;

    while (is_pid_running(pid)) {
        FILE* smaps_rollup_file = fopen(smaps_rollup_path, "r");
        if (!smaps_rollup_file) {
            printf("Process %d ended or cannot open smaps_rollup.\n", pid);
            break;
        }

        unsigned long rss = 0, pss = 0, swap_pss = 0;
        char line[256], output_file[512], datetime[128];
        time_t now = time(NULL);
        strftime(datetime, sizeof(datetime), "%Y%m%d", localtime(&now));

        while (fgets(line, sizeof(line), smaps_rollup_file)) {
            sscanf(line, "Rss: %lu kB", &rss);
            sscanf(line, "Pss: %lu kB", &pss);
            sscanf(line, "SwapPss: %lu kB", &swap_pss);
        }
        fclose(smaps_rollup_file);

        if (swap_pss != prev_swap_pss) {
            file_suffix++; // Increment suffix for new file creation
            snprintf(output_file, sizeof(output_file), "%s_%s_%d_swaps", base_output_file, datetime, file_suffix);
            if (process_pid(pid, output_file) != 0) {
                printf("Error processing PID. Renaming output file and retrying...\n");

                // Construct the new file name with a "_read_error" suffix
                char new_file_name[1024];
                snprintf(new_file_name, sizeof(new_file_name), "%s_read_error", output_file);
                
                // Attempt to rename the file
                if (rename(output_file, new_file_name) != 0) {
                    perror("Error renaming file on failure");
                }

                usleep(0.5 * 1000);
                continue; // Retry on error
                
                
            }
        }
        else if ((pss - prev_pss) > THRESHOLD){     //|| (rss - prev_rss) > THRESHOLD) {
            file_suffix++; // Update suffix for new file creation
            snprintf(output_file, sizeof(output_file), "%s_%s_%d", base_output_file, datetime, file_suffix);
            if (process_pid(pid, output_file) != 0) {
                printf("Error processing PID. Renaming output file and retrying...\n");

                // Construct the new file name with a "_read_error" suffix
                char new_file_name[1024];
                snprintf(new_file_name, sizeof(new_file_name), "%s_read_error", output_file);
                
                // Attempt to rename the file
                if (rename(output_file, new_file_name) != 0) {
                    perror("Error renaming file on failure");
                }

                usleep(0.5 * 1000);
                continue; // Retry on error
                
                
            }
        }

        prev_rss = rss;
        prev_pss = pss;
        prev_swap_pss = swap_pss;

        usleep(CHECK_INTERVAL * 1000); // Wait before next check
    }

    printf("Monitoring ended for PID %d.\n", pid);
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <PID> <output_file>\n", argv[0]);
        return 1;
    }

    pid_t pid = strtoul(argv[1], NULL, 0);
    const char* output_file = argv[2];

    monitor_and_capture(pid, output_file);

    return 0;
}
