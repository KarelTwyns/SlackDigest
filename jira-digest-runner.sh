#!/bin/bash

# Jira Digest Launch Agent Runner
# Runs digest once per day when machine starts

# Configuration
SCRIPT_DIR="/Users/karelandriessen/Instanties/copilot-worktrees/SlackDigest/kareltwyns-potential-guide"
PYTHON_SCRIPT="$SCRIPT_DIR/jira_digest.py"
LOG_DIR="$HOME/.jira-digest-logs"
LOG_FILE="$LOG_DIR/digest.log"
STATE_FILE="$HOME/.jira-digest-state"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check if we've already run today
TODAY=$(date +%Y-%m-%d)
LAST_RUN=$(cat "$STATE_FILE" 2>/dev/null || echo "never")

if [ "$LAST_RUN" = "$TODAY" ]; then
    log_message "Already ran today ($TODAY), skipping"
    exit 0
fi

log_message "Starting Jira digest automation (last run: $LAST_RUN)"

# Source environment variables from ~/.zshrc
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc"
fi

# Run the digest script
cd "$SCRIPT_DIR"
python3 "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    # Update last run date
    echo "$TODAY" > "$STATE_FILE"
    log_message "✓ Digest completed successfully"
else
    log_message "✗ Digest failed with exit code $?"
fi
