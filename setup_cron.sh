#!/bin/bash

# Script to setup cron job for daily stormwater app execution
# This script helps configure the cron job to run the app daily

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run_app.sh"

echo "Setting up daily cron job for stormwater app..."
echo "Script location: $RUN_SCRIPT"

# Check if run_app.sh exists and is executable
if [ ! -f "$RUN_SCRIPT" ]; then
    echo "ERROR: run_app.sh not found at $RUN_SCRIPT"
    exit 1
fi

if [ ! -x "$RUN_SCRIPT" ]; then
    echo "Making run_app.sh executable..."
    chmod +x "$RUN_SCRIPT"
fi

# Ask user for preferred execution time
echo ""
echo "When would you like the app to run daily?"
echo "Please enter the time in 24-hour format (HH:MM):"
echo "Examples: 09:00 for 9 AM, 14:30 for 2:30 PM, 23:00 for 11 PM"
read -p "Time (HH:MM): " time_input

# Validate time format
if [[ ! $time_input =~ ^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$ ]]; then
    echo "ERROR: Invalid time format. Please use HH:MM format (e.g., 09:00)"
    exit 1
fi

# Extract hour and minute
hour=$(echo $time_input | cut -d: -f1)
minute=$(echo $time_input | cut -d: -f2)

# Remove leading zeros for cron
hour=$((10#$hour))
minute=$((10#$minute))

# Create cron job entry
CRON_JOB="$minute $hour * * * $RUN_SCRIPT"

echo ""
echo "Cron job to be added:"
echo "$CRON_JOB"
echo ""
echo "This will run the stormwater app daily at $time_input"
echo ""

# Ask for confirmation
read -p "Do you want to add this cron job? (y/N): " confirm

if [[ $confirm =~ ^[Yy]$ ]]; then
    # Backup current crontab
    echo "Backing up current crontab..."
    crontab -l > "$SCRIPT_DIR/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null || echo "No existing crontab found"
    
    # Add new cron job
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    
    echo "✅ Cron job added successfully!"
    echo ""
    echo "The stormwater app will now run daily at $time_input"
    echo ""
    echo "To view your current cron jobs: crontab -l"
    echo "To remove this cron job later: crontab -e (then delete the line)"
    echo ""
    echo "Logs will be saved in: $SCRIPT_DIR/logs/"
    echo ""
    echo "Note: Make sure to:"
    echo "1. Create a .env file based on .env.example with your credentials"
    echo "2. Ensure your Mac doesn't sleep during the scheduled time"
    echo "3. Grant necessary permissions to Terminal/cron if prompted"
else
    echo "Cron job setup cancelled."
    echo ""
    echo "To set up manually, add this line to your crontab (crontab -e):"
    echo "$CRON_JOB"
fi

echo ""
echo "Setup complete!"