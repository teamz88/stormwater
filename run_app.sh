#!/bin/bash

# Script to run the stormwater app with proper environment setup
# This script should be scheduled to run daily
# Usage: ./run_app.sh [--date YYYY-MM-DD]

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Log file for cron output
LOG_FILE="$SCRIPT_DIR/logs/app_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting stormwater app execution..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    log "ERROR: .env file not found. Please create it based on .env.example"
    exit 1
fi

# Load environment variables
set -a  # automatically export all variables
source .env
set +a

# Check if required environment variables are set
required_vars=("STORMWATER_USERNAME" "STORMWATER_PASSWORD" "STORMWATER_REPORT_URL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        log "ERROR: Environment variable $var is not set"
        exit 1
    fi
done

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
log "Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
log "Installing/updating requirements..."
pip install -r requirements.txt

# Run the application
log "Running stormwater application..."
if [ "$1" = "--date" ] && [ -n "$2" ]; then
    log "Running with custom date: $2"
    python app.py --date "$2" 2>&1 | tee -a "$LOG_FILE"
else
    log "Running with default behavior (latest date)"
    python app.py 2>&1 | tee -a "$LOG_FILE"
fi

# Check exit status
if [ $? -eq 0 ]; then
    log "Application completed successfully"
else
    log "Application failed with exit code $?"
    exit 1
fi

# Clean up old log files (keep last 30 days)
find "$SCRIPT_DIR/logs" -name "app_*.log" -mtime +30 -delete 2>/dev/null || true

log "Script execution completed"