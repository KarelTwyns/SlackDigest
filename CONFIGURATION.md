# Configuration Guide

The digest automation reads all settings from `digest-config.json`. You can customize behavior without touching any code.

## Quick Start

Edit `digest-config.json` to adjust:

### 1. Keywords That Trigger "Needs Discussion"

```json
"discussion_keywords": [
  "crash",
  "bug", 
  "error",
  "broken",
  "failed"
]
```

Add or remove keywords that indicate a ticket needs team attention.

### 2. Routine Keywords (Excluded From Discussion)

```json
"routine_keywords": [
  "cjib",
  "export",
  "data export"
]
```

Tickets matching these keywords are marked as routine (no discussion needed).

### 3. Critical Keywords (High Priority)

```json
"critical_keywords": [
  "crash",
  "critical",
  "urgent",
  "production"
]
```

Tickets with these keywords are flagged as High priority in the digest.

### 4. Slack Display Options

```json
"slack": {
  "show_routine_section": true,
  "max_routine_items_shown": 5,
  "show_broken_tickets": true
}
```

- `show_routine_section`: Show routine tickets in Slack digest
- `max_routine_items_shown`: How many routine tickets to display before collapsing
- `show_broken_tickets`: Show tickets with missing descriptions

### 5. Jira Scanning Options

```json
"jira": {
  "hours_lookback": 24,
  "max_id_scan_range": 500,
  "consecutive_404_threshold": 50
}
```

- `hours_lookback`: How many hours back to look for tickets (default: 24)
- `max_id_scan_range`: How many issue IDs to scan forward for new tickets
- `consecutive_404_threshold`: Stop scanning after this many consecutive 404s

## Examples

### Add a Keyword

To flag tickets with "outage" as needing discussion:

```json
"discussion_keywords": [
  "crash",
  "bug",
  "error",
  "broken",
  "failed",
  "outage"  // ← Add this
]
```

### Exclude a Category

To also exclude "API" issues (treat as routine):

```json
"routine_keywords": [
  "cjib",
  "export",
  "data export",
  "api documentation"  // ← Add this
]
```

### Hide Routine Issues from Slack

```json
"slack": {
  "show_routine_section": false  // ← Change to false
}
```

## Testing Changes

After editing `digest-config.json`:

1. **Test locally** by running:
   ```bash
   cd /Users/karelandriessen/Instanties/copilot-worktrees/SlackDigest/kareltwyns-potential-guide
   source ~/.zshrc
   python3 jira_digest.py
   ```

2. **Reset the daily-run state** (to test Launch Agent):
   ```bash
   rm ~/.jira-digest-state
   ```

3. **Verify in Slack** that changes took effect

## No Restart Needed

Changes to `digest-config.json` take effect immediately on the next run. No need to restart anything!
