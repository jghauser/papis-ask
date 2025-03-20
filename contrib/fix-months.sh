#!/usr/bin/env bash

# Function to convert month name to number with leading zero
month_to_number() {
    local month="${1,,}"  # Convert to lowercase for case-insensitive matching
    case "$month" in
        january|jan)     echo "1" ;;
        february|feb)    echo "2" ;;
        march|mar)       echo "3" ;;
        april|apr)       echo "4" ;;
        may)             echo "5" ;;
        june|jun)        echo "6" ;;
        july|jul)        echo "7" ;;
        august|aug)      echo "8" ;;
        september|sep)   echo "9" ;;
        october|oct)     echo "10" ;;
        november|nov)    echo "11" ;;
        december|dec)    echo "12" ;;
        *)               echo "" ;;
    esac
}

# Check if input file is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <input-file>"
    exit 1
fi

input_file="$1"

# Process each line in the input file
while IFS=$'\t' read -r _ _ path || [ -n "$path" ]; do
    # Skip empty lines
    [ -z "$path" ] && continue

    info_file="$path/info.yaml"

    # Check if info.yaml exists
    if [ ! -f "$info_file" ]; then
        echo "Error: $info_file does not exist"
        continue
    fi

    # Extract the month value from info.yaml
    month_line=$(grep -E "^month:" "$info_file" || echo "")

    if [ -z "$month_line" ]; then
        echo "Error: No month field found in $info_file"
        continue
    fi

    # Extract the month name
    month_name=$(echo "$month_line" | sed -E 's/^month:\s*//')

    # Convert month name to number
    month_num=$(month_to_number "$month_name")

    if [ -z "$month_num" ]; then
        echo "Error: Could not convert month '$month_name' to number in $info_file"
        continue
    fi

    # Replace the month name with the number in the file
    if sed -i "s/^month:.*$/month: $month_num/" "$info_file"; then
        echo "Updated $info_file: $month_name → $month_num"
    else
        echo "Error: Failed to update $info_file"
    fi

done < "$input_file"

echo "Processing complete!"
