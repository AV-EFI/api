#!/bin/bash

# Set up error handling
set -e

# Output directory
OUTPUT_DIR="code_analysis"
mkdir -p "${OUTPUT_DIR}"

# Output files
CC_FILE="${OUTPUT_DIR}/cyclomatic_complexity.txt"
RAW_FILE="${OUTPUT_DIR}/raw_metrics.txt"
HAL_FILE="${OUTPUT_DIR}/halstead_metrics.txt"
MI_FILE="${OUTPUT_DIR}/maintainability_index.txt"

# Check if radon is installed
if ! command -v radon &> /dev/null; then
    echo "Radon is not installed. Installing now..."
    pip install radon
fi

# Function to run analysis and display results
run_analysis() {
    local file=$1
    local title=$2
    
    # Clear existing file if it exists
    > "${file}"
    
    # Add header
    echo "=== ${title} ===" > "${file}"
    
    # Run analysis
    echo "Generating ${title}..."
    if [[ -f "${file}" ]]; then
        # Use find to get all Python files excluding venv directory
        find . -type f -name "*.py" -not -path "./venv/*" -not -path "./tests/*" -not -name "__init__.py" -print0 | xargs -0 $3 >> "${file}"
        echo "Results saved to ${file}"
    else
        echo "Error: Could not create ${file}"
        exit 1
    fi
}

# Run each analysis type
run_analysis "${CC_FILE}" "Cyclomatic Complexity" "radon cc -a -s"
run_analysis "${RAW_FILE}" "Raw Metrics" "radon raw -s"
run_analysis "${HAL_FILE}" "Halstead Metrics" "radon hal"
run_analysis "${MI_FILE}" "Maintainability Index" "radon mi -s"

echo "Analysis complete. All reports are stored in the ${OUTPUT_DIR} directory."