#!/usr/bin/env bash

# Exit on error
set -e

# Check for required dependencies
for cmd in pdfinfo pdftotext ocrmypdf; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: Required command '$cmd' not found in PATH."
    echo "Please install the necessary packages:"
    echo "  - pdfinfo, pdftotext: poppler-utils package"
    echo "  - ocrmypdf: ocrmypdf package"
    exit 1
  fi
done

if [ $# -lt 1 ]; then
  echo "Usage: $0 <directory_to_search>"
  exit 1
fi

SEARCH_DIR="$1"
BACKUP_DIR="${SEARCH_DIR}/ocr_backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Find all PDF files in the directory
find "$SEARCH_DIR" -type f -name "*.pdf" | while read -r pdf_file; do
  # Skip files in the backup directory
  if [[ "$pdf_file" == *"$BACKUP_DIR"* ]]; then
    continue
  fi

  # Check if the PDF is faulty or just one page long
  if ! pdfinfo "$pdf_file" >/dev/null 2>&1; then
    echo "⚠️ WARNING. Faulty PDF detected: $pdf_file"
    continue
  fi

  # Get page count
  page_count=$(pdfinfo "$pdf_file" 2>/dev/null | grep -a "Pages:" | awk '{print $2}')

  # Check if PDF is only one page
  if [ "$page_count" = "1" ]; then
    echo "ℹ️ WARNING. Single-page PDF detected: $pdf_file"
  fi

  # Check if the PDF has extractable text
  # Create a temporary file for text extraction
  temp_txt=$(mktemp)
  pdftotext -l 5 "$pdf_file" "$temp_txt" 2>/dev/null

  # Check if extracted text file is empty (or nearly empty)
  if [ ! -s "$temp_txt" ] || [ "$(stat -c%s "$temp_txt")" -lt 50 ]; then
    echo "Processing: $pdf_file (no text found)"

    # Create backup with directory structure
    rel_path="${pdf_file#"$SEARCH_DIR"/}"
    backup_path="${BACKUP_DIR}/${rel_path}"
    backup_dir=$(dirname "$backup_path")
    mkdir -p "$backup_dir"

    # Copy original to backup
    cp "$pdf_file" "$backup_path"

    # OCR the file in place, preserving annotations
    ocrmypdf --redo-ocr --output-type pdf "$pdf_file" "$pdf_file.tmp"

    # Replace original with OCR'd version
    mv "$pdf_file.tmp" "$pdf_file"

    echo "✓ OCR completed: $pdf_file (backup at $backup_path)"
  fi

  # Clean up temporary file
  rm -f "$temp_txt"
done

echo "=== All non-text PDFs have been processed! ==="
