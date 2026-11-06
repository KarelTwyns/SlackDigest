# Customizing Automation Instructions

You have **three ways** to customize the digest automation:

## 1️⃣ Config File (Keywords & Display) - No Code Required

Edit `digest-config.json` to change:
- ✅ Keywords that trigger "needs discussion"
- ✅ Routine keywords (excluded from discussion)
- ✅ Critical keywords (high priority flags)
- ✅ Slack display options (what sections to show)
- ✅ Jira scan behavior

**Example:**
```json
{
  "analysis": {
    "discussion_keywords": ["crash", "bug", "error", "your-keyword-here"],
    "routine_keywords": ["cjib", "export", "add-more-here"]
  }
}
```

Changes take effect immediately on next run. See `CONFIGURATION.md` for details.

---

## 2️⃣ Copilot Automation UI (Instructions & Logic) - Natural Language

Use the **"Jira Digest (Configurable)"** automation from the Copilot Automations panel:

1. Open **Copilot Automations** in the app
2. Find **"Jira Digest (Configurable)"**
3. Click **"Edit"** or **"Run"**
4. Ask for changes in natural language:

**Examples:**
- "Make descriptions more verbose with more details about each ticket"
- "Include ticket priority level in the digest"
- "Only flag P0/P1 issues as needing discussion"
- "Add emoji indicators for different ticket types"
- "Change the Slack formatting to be more compact"
- "Include comments/replies in the analysis"
- "Flag tickets that haven't been updated in 3+ days"

The automation will:
- Understand your request
- Update the Python script accordingly
- Test the changes
- Show you the modified digest

---

## 3️⃣ Direct Python Edits (Advanced) - Full Control

Edit `jira_digest.py` directly if you want to:
- Change the analysis algorithm completely
- Add new data sources
- Integrate with other APIs
- Implement custom logic

**Key methods to modify:**
- `analyze_tickets()` - Main analysis logic
- `assess_discussion_need()` - Discussion flagging logic
- `format_slack_message()` - Slack message formatting

---

## Recommended Workflow

1. **Start simple** → Use `digest-config.json` for keywords
2. **Need formatting changes?** → Tell the Copilot automation what you want
3. **Need complex logic?** → Edit `jira_digest.py` or ask the automation to do it

The Copilot automation is your **easiest path** for most changes. Just describe what you want!
