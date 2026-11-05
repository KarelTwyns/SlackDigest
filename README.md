# Jira Service Desk Digest Automation

This automation fetches Jira Service Desk tickets created in the last 24 hours, analyzes them for issues, and posts a formatted digest to Slack.

## Features

- **Ticket Fetching**: Retrieves all tickets created in the last 24 hours from Jira
- **Priority Analysis**: Categorizes tickets by priority level
- **Issue Detection**:
  - 🔴 **Broken Tickets**: Unassigned tickets in Open/To Do/New status
  - 🤔 **Unanswered Tickets**: Tickets with no description (likely incomplete)
  - ⚠️ **Priority Issues**: High/Critical priority tickets not yet in progress

## Requirements

- Python 3.7+
- `requests` library

## Setup

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Variables

Set the following environment variables before running:

```bash
export JIRA_URL="https://your-jira-instance.atlassian.net"
export JIRA_USERNAME="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**How to get these values:**

- **JIRA_URL**: Your Jira Cloud instance URL
- **JIRA_USERNAME**: Your Jira email address
- **JIRA_API_TOKEN**: Generate at https://id.atlassian.com/manage-profile/security/api-tokens
- **SLACK_WEBHOOK_URL**: Create an Incoming Webhook at https://api.slack.com/messaging/webhooks

## Usage

### Run the Digest

```bash
python3 jira_digest.py
```

### Example Output

The script will:
1. Connect to Jira and fetch tickets from the last 24 hours
2. Analyze them for priority, status, and assignment issues
3. Format the analysis into a Slack message with:
   - Total ticket count and priority breakdown
   - List of broken/unassigned tickets
   - List of unanswered tickets
   - List of high-priority tickets not in progress
4. Post the formatted message to Slack

## Scheduling

To run this automatically, you can:

### Using Cron (Linux/macOS)
```bash
# Run at 9 AM every weekday
0 9 * * 1-5 cd /path/to/repo && /usr/bin/python3 jira_digest.py
```

### Using GitHub Actions
Create `.github/workflows/jira-digest.yml`:
```yaml
name: Jira Digest
on:
  schedule:
    - cron: '0 9 * * 1-5'

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python3 jira_digest.py
        env:
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USERNAME: ${{ secrets.JIRA_USERNAME }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Error Handling

The script will:
- Exit with code 1 if any required environment variables are missing
- Exit with code 1 if Jira API calls fail
- Exit with code 1 if Slack posting fails
- Continue processing with warnings if individual ticket analysis fails

## License

MIT
