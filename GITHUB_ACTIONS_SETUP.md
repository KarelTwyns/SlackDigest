# GitHub Actions Setup Guide

This repository includes a GitHub Actions workflow that runs the Jira digest automation on a schedule, even when your machine is off.

## ⚙️ Setup Steps

### 1. Push to GitHub
Make sure your repository is pushed to GitHub:
```bash
git push origin kareltwyns-jira-digest-automation
```

### 2. Create Repository Secrets
You need to add 4 secrets to your GitHub repository so the workflow can access Jira and Slack:

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these 4 secrets:

| Secret Name | Value |
|---|---|
| `JIRA_URL` | Your Jira instance URL (e.g., `https://parkius.atlassian.net`) |
| `JIRA_USERNAME` | Your Jira username/email |
| `JIRA_API_TOKEN` | Your Jira API token (from [Jira account settings](https://id.atlassian.com/manage-profile/security/api-tokens)) |
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL (from Slack app configuration) |

⚠️ **Important:** These secrets are encrypted and never visible in logs or workflow runs.

### 3. Verify the Workflow
1. Go to your repository on GitHub
2. Click **Actions** tab
3. You should see "Jira Service Desk Digest" workflow listed
4. (Optional) Click it and click **Run workflow** to test manually

## 📅 Schedule

The workflow runs automatically:
- **Daily at 9 AM UTC** (10 AM CET)
- Can also be triggered manually from the Actions tab
- Adjust the schedule by editing `.github/workflows/jira-digest.yml` (line 6):
  ```yaml
  - cron: '0 9 * * *'  # Change to your preferred time
  ```

See [cron syntax documentation](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule) for other schedule patterns.

## 🔍 Monitoring

After setting up secrets:
1. Go to **Actions** tab
2. Click on a workflow run to see logs
3. Digest results are posted to your Slack webhook

## 🆘 Troubleshooting

**Workflow not running?**
- Check that secrets are configured correctly
- Verify the workflow file exists at `.github/workflows/jira-digest.yml`
- Check **Actions** tab for error logs

**Secrets not found error?**
- Make sure secret names match exactly (case-sensitive)
- Verify you added them to the correct repository (not organization)

**Python/dependency errors?**
- Ensure `requirements.txt` is in the repository root
- Check Python version in workflow (currently 3.11)
