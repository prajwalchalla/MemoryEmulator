import argparse

def process_files(input_file_name, output_file_name):
    # Open the input file for reading
    with open(input_file_name, 'r') as input_file:
        # Read all lines from the input file
        lines = input_file.readlines()

    # Open the output file for writing
    with open(output_file_name, 'w') as output_file:
        # Filter lines that contain "BlockID :" and write them to the output file
        lines_to_keep = [line for line in lines if "CXL_BLK_ID :" not in line]
        output_file.writelines(line for line in lines if "CXL_BLK_ID :" in line)

    # Open the input file again for writing to overwrite it with lines to keep
    with open(input_file_name, 'w') as input_file:
        # Write the lines that do not contain "BlockID :" back to the input file
        input_file.writelines(lines_to_keep)

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Process input and output files.')
    parser.add_argument('input_file', help='The input file to process')
    parser.add_argument('output_file', help='The file to write the processed lines to')

    # Parse the arguments
    args = parser.parse_args()

    # Process the files
    process_files(args.input_file, args.output_file)

if __name__ == '__main__':
    main()
