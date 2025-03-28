#!/bin/bash

# Force CPU usage for PyTorch
export PYTORCH_ENABLE_MPS_FALLBACK=1
export MARKER_DEVICE=cpu

# Get folder path from command line or use default
FOLDER=${1:-"meta_invoices"}
OUTPUT=${2:-"parsed_data.xlsx"}

echo "Running OCR on folder: $FOLDER, output: $OUTPUT"

# Run the OCR program
python ocr_openai.py --folder $FOLDER --output $OUTPUT --memory-check 