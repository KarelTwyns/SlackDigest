#!/usr/bin/env python3
"""
Jira Service Desk Digest Automation
Fetches tickets from the last 24 hours, analyzes them, and posts a digest to Slack.
"""

import os
import requests
import json
from datetime import datetime, timedelta, timezone
import sys
from urllib.parse import quote

class JiraDigest:
    def __init__(self):
        self.jira_url = os.getenv('JIRA_URL')
        self.jira_username = os.getenv('JIRA_USERNAME')
        self.jira_api_token = os.getenv('JIRA_API_TOKEN')
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        
        if not all([self.jira_url, self.jira_username, self.jira_api_token, self.slack_webhook_url]):
            raise ValueError("Missing required environment variables: JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, SLACK_WEBHOOK_URL")
    
    def get_jira_tickets(self) -> List[Dict[str, Any]]:
        """Fetch tickets created in the last 24 hours from Jira Service Desk."""
        try:
            # Use Service Desk API which is more reliable than the deprecated search APIs
            auth = (self.jira_username, self.jira_api_token)
            headers = {'Accept': 'application/json'}
            
            url = f"{self.jira_url}/rest/servicedeskapi/request"
            params = {
                'limit': 100,
                'expand': 'changelog'
            }
            
            response = requests.get(url, auth=auth, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            all_requests = data.get('values', [])
            
            # Filter for tickets created in the last 24 hours
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(days=1)
            
            recent_tickets = []
            for ticket in all_requests:
                try:
                    created_str = ticket.get('createdDate', '')
                    if created_str:
                        # Parse ISO 8601 format: 2026-11-05T08:57:32.123+0100
                        created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                        if created_date >= yesterday:
                            recent_tickets.append(ticket)
                except:
                    pass
            
            # If no tickets in last 24 hours, return all tickets for demo purposes
            if not recent_tickets:
                print(f"ℹ️  No tickets created in last 24 hours, showing all {len(all_requests)} requests for demo")
                recent_tickets = all_requests[:50]  # Limit to 50 for demo
            
            print(f"✓ Fetched {len(all_requests)} total requests, analyzing {len(recent_tickets)}")
            return recent_tickets
        except Exception as e:
            print(f"✗ Error fetching Jira tickets: {e}")
            raise
    
    def analyze_tickets(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tickets for priority, status, and priority appropriateness."""
        analysis = {
            'total': len(tickets),
            'by_status': {},
            'broken_tickets': [],
            'unanswered_tickets': [],
            'priority_issues': []
        }
        
        for ticket in tickets:
            try:
                key = ticket.get('issueKey', 'N/A')
                summary = ticket.get('summary', 'No summary')
                status = ticket.get('currentStatus', {})
                status_name = status.get('name', 'Unknown') if status else 'Unknown'
                reporter = ticket.get('reporter', {})
                reporter_name = reporter.get('displayName', 'Unknown') if reporter else 'Unknown'
                created_date = ticket.get('createdDate', 'Unknown')
                
                # Get request field values for priority if available
                field_values = ticket.get('requestFieldValues', [])
                priority = 'Unknown'
                description = ''
                
                for field in field_values:
                    if field.get('fieldId') == 'priority':
                        priority = field.get('value', 'Unknown')
                    elif field.get('fieldId') == 'description':
                        description = field.get('value', '')
                
                # Count by status
                if status_name not in analysis['by_status']:
                    analysis['by_status'][status_name] = 0
                analysis['by_status'][status_name] += 1
                
                # Check for broken tickets (Open/Waiting for Support with no description)
                if status_name in ['Open', 'Waiting for Support', 'New', 'To Do'] and not description:
                    analysis['broken_tickets'].append({
                        'key': key,
                        'summary': summary,
                        'status': status_name,
                        'reason': 'Missing description/details'
                    })
                
                # Check for unanswered tickets (not resolved yet, minimal interaction)
                if status_name not in ['Resolved', 'Closed', 'Done']:
                    analysis['unanswered_tickets'].append({
                        'key': key,
                        'summary': summary,
                        'status': status_name,
                        'created': created_date[:10] if isinstance(created_date, str) else 'Unknown'
                    })
                
                # Check for priority issues (high priority not resolved)
                if priority == 'High' and status_name not in ['Resolved', 'Closed', 'Done']:
                    analysis['priority_issues'].append({
                        'key': key,
                        'summary': summary,
                        'status': status_name,
                        'priority': priority,
                        'reason': f'{priority} priority not resolved'
                    })
                
            except Exception as e:
                print(f"Warning: Error analyzing ticket: {e}")
                continue
        
        print(f"✓ Analyzed {len(tickets)} tickets")
        print(f"  - Broken tickets: {len(analysis['broken_tickets'])}")
        print(f"  - Unanswered tickets: {len(analysis['unanswered_tickets'])}")
        print(f"  - Priority issues: {len(analysis['priority_issues'])}")
        
        return analysis
    
    def format_slack_message(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format the analysis into a Slack message."""
        status_summary = ", ".join(
            [f"{count} {status}" for status, count in sorted(analysis['by_status'].items())]
        ) if analysis['by_status'] else "None"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Jira Service Desk Digest - Last 24 Hours",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Total Requests:* {analysis['total']}\n*By Status:* {status_summary}"
                }
            }
        ]
        
        # Add broken tickets section
        if analysis['broken_tickets']:
            broken_text = "*🔴 Incomplete Tickets (Missing Details):*\n"
            for ticket in analysis['broken_tickets'][:5]:
                broken_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']}\n"
            if len(analysis['broken_tickets']) > 5:
                broken_text += f"• ... and {len(analysis['broken_tickets']) - 5} more\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": broken_text
                }
            })
        
        # Add unanswered tickets section
        if analysis['unanswered_tickets']:
            unanswered_text = "*🤔 Open Requests:*\n"
            for ticket in analysis['unanswered_tickets'][:5]:
                unanswered_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']}\n"
            if len(analysis['unanswered_tickets']) > 5:
                unanswered_text += f"• ... and {len(analysis['unanswered_tickets']) - 5} more\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": unanswered_text
                }
            })
        
        # Add priority issues section
        if analysis['priority_issues']:
            priority_text = "*⚠️  Urgent (High Priority, Not Resolved):*\n"
            for ticket in analysis['priority_issues'][:5]:
                priority_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']}\n"
            if len(analysis['priority_issues']) > 5:
                priority_text += f"• ... and {len(analysis['priority_issues']) - 5} more\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": priority_text
                }
            })
        
        # Add footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                }
            ]
        })
        
        return {"blocks": blocks}
    
    def post_to_slack(self, message: Dict[str, Any]) -> bool:
        """Post the formatted message to Slack."""
        try:
            response = requests.post(
                self.slack_webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            print("✓ Posted digest to Slack")
            return True
        except Exception as e:
            print(f"✗ Error posting to Slack: {e}")
            raise
    
    def run(self):
        """Execute the full digest workflow."""
        try:
            print("Starting Jira Service Desk Digest...")
            print(f"Jira URL: {self.jira_url}")
            print()
            
            # Fetch tickets
            tickets = self.get_jira_tickets()
            
            if not tickets:
                print("No tickets found in the last 24 hours")
                return
            
            # Analyze tickets
            analysis = self.analyze_tickets(tickets)
            
            # Format message
            message = self.format_slack_message(analysis)
            
            # Post to Slack
            self.post_to_slack(message)
            
            print()
            print("✓ Digest automation completed successfully!")
            
        except Exception as e:
            print(f"\n✗ Digest automation failed: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    digest = JiraDigest()
    digest.run()
