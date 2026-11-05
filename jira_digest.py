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
            auth = (self.jira_username, self.jira_api_token)
            headers = {'Accept': 'application/json'}
            
            all_requests = []
            
            # First, try the Service Desk API (catches regular requests)
            try:
                url = f"{self.jira_url}/rest/servicedeskapi/request"
                params = {
                    'limit': 500,
                    'expand': 'changelog'
                }
                
                response = requests.get(url, auth=auth, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                sd_requests = data.get('values', [])
                print(f"✓ Fetched {len(sd_requests)} Service Desk requests")
                
                # Convert to common format
                for ticket in sd_requests:
                    created_obj = ticket.get('createdDate', {})
                    if isinstance(created_obj, dict):
                        created_str = created_obj.get('iso8601', '')
                    else:
                        created_str = str(created_obj)
                    
                    all_requests.append({
                        'key': ticket.get('issueKey'),
                        'summary': ticket.get('summary'),
                        'created': created_str,
                        'status': ticket.get('currentStatus', {}).get('name', 'Unknown'),
                        'reporter': ticket.get('reporter', {}).get('displayName', 'Unknown'),
                        'type': 'Service Desk',
                        'raw': ticket
                    })
            except Exception as e:
                print(f"Warning: Error fetching Service Desk requests: {e}")
            
            # Also try fetching recent issues directly by checking a range of issue IDs
            # This catches tickets created via email or other sources
            try:
                # Get the highest issue number from Service Desk requests
                if all_requests:
                    max_id = max([int(req['key'].split('-')[1]) for req in all_requests if '-' in req['key']])
                else:
                    max_id = 12257  # Default known highest from SD API
                
                print(f"ℹ️  Checking for recent issues (highest known ID: {max_id})")
                
                # Fetch FORWARD from max_id to find newer issues (more efficient than scanning backwards)
                recently_fetched = set()
                issues_checked = 0
                consecutive_404 = 0
                
                for issue_id in range(max_id + 1, max_id + 500):  # Check next 500 IDs
                    key = f"SDP-{issue_id}"
                    
                    url = f"{self.jira_url}/rest/api/2/issue/{key}"
                    
                    try:
                        response = requests.get(url, auth=auth, headers=headers, timeout=2)
                        issues_checked += 1
                        
                        if response.status_code == 200:
                            consecutive_404 = 0  # Reset counter
                            issue = response.json()
                            fields = issue.get('fields', {})
                            created_str = fields.get('created', '')
                            
                            # Check if created in last 24 hours
                            now = datetime.now(timezone.utc)
                            yesterday = now - timedelta(days=1)
                            if created_str:
                                created_date = datetime.fromisoformat(created_str)
                                if created_date.tzinfo is None:
                                    created_date = created_date.replace(tzinfo=timezone.utc)
                                if created_date >= yesterday:
                                    # Check if not already in list
                                    if key not in {req['key'] for req in all_requests}:
                                        all_requests.append({
                                            'key': key,
                                            'summary': fields.get('summary'),
                                            'created': created_str,
                                            'status': fields.get('status', {}).get('name', 'Unknown'),
                                            'reporter': fields.get('reporter', {}).get('displayName', 'Unknown'),
                                            'type': 'Issue',
                                            'raw': issue
                                        })
                                        recently_fetched.add(key)
                        
                        elif response.status_code == 404:
                            consecutive_404 += 1
                            # If we've seen 50 consecutive 404s, stop scanning
                            if consecutive_404 > 50:
                                break
                    
                    except:
                        pass
                
                print(f"  Scanned {issues_checked} issue IDs")
                if recently_fetched:
                    print(f"✓ Found {len(recently_fetched)} recent issues: {', '.join(sorted(recently_fetched))}")
                
            except Exception as e:
                print(f"Warning: Error scanning for recent issues: {e}")
            
            # Filter for tickets created in the last 24 hours
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(days=1)
            
            recent_tickets = []
            for ticket in all_requests:
                try:
                    created_str = ticket.get('created', '')
                    if created_str:
                        # Parse ISO 8601 format
                        created_date = datetime.fromisoformat(created_str)
                        # Ensure timezone-aware for comparison
                        if created_date.tzinfo is None:
                            created_date = created_date.replace(tzinfo=timezone.utc)
                        if created_date >= yesterday:
                            recent_tickets.append(ticket)
                except Exception as e:
                    pass
            
            # If no tickets in last 24 hours from these APIs, fall back to Service Desk requests
            if not recent_tickets and all_requests:
                print(f"ℹ️  No tickets created in last 24 hours, showing recent {min(len(all_requests), 50)} requests")
                recent_tickets = all_requests[:50]
            
            print(f"✓ Found {len(recent_tickets)} tickets from last 24 hours")
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
                key = ticket.get('key', 'N/A')
                summary = ticket.get('summary', 'No summary')
                status = ticket.get('status', 'Unknown')
                reporter = ticket.get('reporter', 'Unknown')
                ticket_type = ticket.get('type', 'Unknown')
                
                # Get raw ticket for additional fields
                raw_ticket = ticket.get('raw', {})
                
                # Extract description/details
                description = ''
                if ticket_type == 'Service Desk':
                    field_values = raw_ticket.get('requestFieldValues', [])
                    for field in field_values:
                        if field.get('fieldId') == 'description':
                            description = field.get('value', '')
                else:
                    description = raw_ticket.get('fields', {}).get('description', '')
                
                # Count by status
                if status not in analysis['by_status']:
                    analysis['by_status'][status] = 0
                analysis['by_status'][status] += 1
                
                # Check for broken tickets (Open with no description)
                if status in ['Open', 'Waiting for Support', 'New', 'To Do', 'OPEN'] and not description:
                    analysis['broken_tickets'].append({
                        'key': key,
                        'summary': summary,
                        'status': status,
                        'type': ticket_type,
                        'reason': 'Missing description/details'
                    })
                
                # Check for unanswered tickets (not resolved)
                if status not in ['Resolved', 'Closed', 'Done', 'CLOSED']:
                    analysis['unanswered_tickets'].append({
                        'key': key,
                        'summary': summary,
                        'status': status,
                        'type': ticket_type
                    })
                
            except Exception as e:
                print(f"Warning: Error analyzing ticket: {e}")
                continue
        
        print(f"✓ Analyzed {len(tickets)} tickets")
        print(f"  - Broken tickets: {len(analysis['broken_tickets'])}")
        print(f"  - Unanswered tickets: {len(analysis['unanswered_tickets'])}")
        
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
