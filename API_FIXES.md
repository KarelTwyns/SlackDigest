# Jira API Issue - Resolution Guide

## Problem
The initial implementation used the deprecated Jira REST API v2 and v3 search endpoints:
- `/rest/api/2/search` → 410 Gone (Deprecated)
- `/rest/api/3/search` → Returns 410 Gone
- `/rest/api/3/search/jql` → Unbounded query error / 400 Bad Request

These endpoints have been deprecated or restricted in Jira Cloud.

## Solution
Use the **Jira Service Desk API** instead:
```
GET /rest/servicedeskapi/request
```

This endpoint:
- ✅ Is actively maintained and reliable
- ✅ Returns all service desk requests with full details
- ✅ Supports pagination (limit, start parameters)
- ✅ Provides createdDate for filtering recent tickets
- ✅ Contains all necessary fields for analysis

## Implementation Details

### Endpoint
```bash
curl -u "username:api_token" \
  "https://your-jira.atlassian.net/rest/servicedeskapi/request?limit=100"
```

### Response Format
```json
{
  "values": [
    {
      "issueKey": "SDP-12345",
      "summary": "Request title",
      "createdDate": "2026-11-05T10:15:32.123+0100",
      "currentStatus": {
        "name": "Open"
      },
      "requestFieldValues": [
        {
          "fieldId": "description",
          "value": "Request details..."
        },
        {
          "fieldId": "priority",
          "value": "High"
        }
      ]
    }
  ]
}
```

### Usage in Automation
```python
# Fetch requests
url = f"{jira_url}/rest/servicedeskapi/request"
response = requests.get(url, auth=(username, token), params={"limit": 100})
requests = response.json()["values"]

# Filter by date
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
for request in requests:
    created = datetime.fromisoformat(request["createdDate"])
    if created >= (now - timedelta(days=1)):
        # Process request
```

## Key Differences from JQL Search API

| Feature | Search API | Service Desk API |
|---------|-----------|-----------------|
| Endpoint | `/rest/api/2/search` or `/rest/api/3/search/jql` | `/rest/servicedeskapi/request` |
| Status | ❌ Deprecated | ✅ Active |
| Fields Available | Limited | Full request details |
| Pagination | maxResults, startAt | limit, start |
| Date Filtering | JQL only | Direct field access |
| Authentication | Basic Auth | Basic Auth |

## Testing the Fix

```bash
# Export your credentials
export JIRA_URL="https://your-jira.atlassian.net"
export JIRA_USERNAME="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
export SLACK_WEBHOOK_URL="your-webhook-url"

# Run the automation
source ~/.zshrc  # or wherever you store credentials
python3 jira_digest.py
```

## Expected Output

```
Starting Jira Service Desk Digest...
Jira URL: https://your-jira.atlassian.net

✓ Fetched 24 total requests, analyzing 24
✓ Analyzed 24 tickets
  - Broken tickets: 5
  - Unanswered tickets: 12
  - Priority issues: 2
✓ Posted digest to Slack

✓ Digest automation completed successfully!
```

## References

- [Jira Service Desk API Documentation](https://developer.atlassian.com/cloud/jira/service-desk/rest/api-group-requests/)
- [Jira Cloud REST API Deprecations](https://developer.atlassian.com/changelog/#CHANGE-2046)
- [API v3 Search JQL Endpoint](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/)
