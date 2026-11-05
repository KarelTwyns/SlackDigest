# Launch Agent Setup

Your Jira digest will now run **automatically once per day when you start your machine**.

## How It Works

1. **At startup**, the Launch Agent runs the digest script
2. **Once per day**, it checks if it's already run today and skips if so
3. **Logs everything** to `~/.jira-digest-logs/` for debugging
4. **Sourcs environment** from `~/.zshrc` so it has access to your Jira/Slack credentials

## Files

- `jira-digest-runner.sh` - Shell script that handles "once per day" logic
- `com.karelandriessen.jira-digest.plist` - macOS Launch Agent configuration
- Installed in: `~/Library/LaunchAgents/com.karelandriessen.jira-digest.plist`

## Logs

Check what happened:
```bash
# Digest execution log
tail -f ~/.jira-digest-logs/digest.log

# Launch Agent system log
tail -f ~/.jira-digest-logs/launchagent.log
```

## Manage It

**Check status:**
```bash
launchctl list | grep jira-digest
```

**Disable it** (if needed):
```bash
launchctl unload ~/Library/LaunchAgents/com.karelandriessen.jira-digest.plist
```

**Re-enable it:**
```bash
launchctl load ~/Library/LaunchAgents/com.karelandriessen.jira-digest.plist
```

**Force run today** (for testing):
```bash
rm ~/.jira-digest-state && bash /Users/karelandriessen/Instanties/copilot-worktrees/SlackDigest/kareltwyns-potential-guide/jira-digest-runner.sh
```

## Backup Plan

You also have **GitHub Actions** running at 9 AM CET daily, so even if the Launch Agent doesn't run, you'll still get your digest from the cloud automation.
