#!/usr/bin/env python3
"""
Jira Service Desk Digest Automation
Fetches tickets from the last 24 hours, analyzes them, and posts a digest to Slack.
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
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
        """Fetch tickets created in the last 24 hours from Jira."""
        try:
            # JQL query for tickets created in the last 24 hours in ServiceDesk project
            # Use project key to restrict the search
            jql = 'project = SDP AND created >= -24h ORDER BY created DESC'
            
            auth = (self.jira_username, self.jira_api_token)
            headers = {'Accept': 'application/json'}
            
            # Using the v2 API which is more stable for Service Desk
            url = f"{self.jira_url}/rest/api/2/search"
            params = {
                'jql': jql,
                'maxResults': 100,
                'fields': 'key,summary,priority,status,assignee,created,updated,description'
            }
            
            response = requests.get(url, auth=auth, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            tickets = data.get('issues', [])
            
            print(f"✓ Fetched {len(tickets)} tickets from Jira")
            return tickets
        except Exception as e:
            print(f"✗ Error fetching Jira tickets: {e}")
            raise
    
    def analyze_tickets(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tickets for priority, status, and priority appropriateness."""
        analysis = {
            'total': len(tickets),
            'by_priority': {},
            'broken_tickets': [],
            'unanswered_tickets': [],
            'priority_issues': []
        }
        
        for ticket in tickets:
            try:
                key = ticket.get('key', 'N/A')
                summary = ticket.get('fields', {}).get('summary', 'No summary')
                priority = ticket.get('fields', {}).get('priority', {})
                priority_name = priority.get('name', 'Unknown') if priority else 'Unknown'
                status = ticket.get('fields', {}).get('status', {})
                status_name = status.get('name', 'Unknown') if status else 'Unknown'
                assignee = ticket.get('fields', {}).get('assignee')
                description = ticket.get('fields', {}).get('description', '')
                
                # Count by priority
                if priority_name not in analysis['by_priority']:
                    analysis['by_priority'][priority_name] = 0
                analysis['by_priority'][priority_name] += 1
                
                # Check for broken tickets (Open/To Do status with no assignee)
                if status_name in ['Open', 'To Do', 'New'] and not assignee:
                    analysis['broken_tickets'].append({
                        'key': key,
                        'summary': summary,
                        'priority': priority_name,
                        'status': status_name,
                        'reason': 'Unassigned'
                    })
                
                # Check for unanswered tickets (Open with minimal description)
                if status_name in ['Open', 'To Do', 'New'] and not description:
                    analysis['unanswered_tickets'].append({
                        'key': key,
                        'summary': summary,
                        'priority': priority_name,
                        'status': status_name,
                        'reason': 'No description'
                    })
                
                # Check for priority issues
                # If ticket is "New" or "To Do" and marked as High/Critical, flag it
                if status_name in ['To Do', 'New'] and priority_name in ['High', 'Highest', 'Critical']:
                    analysis['priority_issues'].append({
                        'key': key,
                        'summary': summary,
                        'priority': priority_name,
                        'status': status_name,
                        'reason': f'{priority_name} priority not in progress'
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
        priority_summary = ", ".join(
            [f"{count} {priority}" for priority, count in sorted(analysis['by_priority'].items())]
        ) if analysis['by_priority'] else "None"
        
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
                    "text": f"*Total Tickets:* {analysis['total']}\n*By Priority:* {priority_summary}"
                }
            }
        ]
        
        # Add broken tickets section
        if analysis['broken_tickets']:
            broken_text = "*🔴 Broken Tickets (Unassigned):*\n"
            for ticket in analysis['broken_tickets'][:5]:
                broken_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']} ({ticket['priority']})\n"
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
            unanswered_text = "*🤔 Unanswered Tickets (No Description):*\n"
            for ticket in analysis['unanswered_tickets'][:5]:
                unanswered_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']} ({ticket['priority']})\n"
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
            priority_text = "*⚠️  Priority Issues (Not In Progress):*\n"
            for ticket in analysis['priority_issues'][:5]:
                priority_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']} ({ticket['priority']})\n"
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
                    "text": f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
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
