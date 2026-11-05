#!/usr/bin/env python3
"""
Jira Service Desk Digest Automation
Fetches tickets from the last 24 hours, analyzes them, and posts a digest to Slack.
"""

import os
import requests
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import sys
from urllib.parse import quote

class JiraDigest:
    def __init__(self, config_path: str = 'digest-config.json'):
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Environment variables
        self.jira_url = os.getenv('JIRA_URL')
        self.jira_username = os.getenv('JIRA_USERNAME')
        self.jira_api_token = os.getenv('JIRA_API_TOKEN')
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        
        if not all([self.jira_url, self.jira_username, self.jira_api_token, self.slack_webhook_url]):
            raise ValueError("Missing required environment variables: JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, SLACK_WEBHOOK_URL")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file not found at {config_path}, using defaults")
            return {
                'analysis': {
                    'discussion_keywords': ['crash', 'bug', 'error', 'broken', 'failed'],
                    'routine_keywords': ['cjib', 'export'],
                    'critical_keywords': ['crash', 'critical', 'urgent'],
                    'min_chars_for_vague_check': 20
                },
                'jira': {
                    'hours_lookback': 24,
                    'max_id_scan_range': 500,
                    'consecutive_404_threshold': 50
                }
            }
    
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
            'needs_discussion': [],
            'routine': [],
            'broken_tickets': [],
            'unanswered_tickets': []
        }
        
        auth = (self.jira_username, self.jira_api_token)
        headers = {'Accept': 'application/json'}
        
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
                
                # Assess if ticket needs team discussion
                needs_discussion_assessment = self.assess_discussion_need(
                    key, summary, description, status, ticket_type
                )
                
                if needs_discussion_assessment['needs_discussion']:
                    analysis['needs_discussion'].append({
                        'key': key,
                        'summary': summary,
                        'reason': needs_discussion_assessment['reason'],
                        'priority': needs_discussion_assessment.get('priority', 'Normal')
                    })
                else:
                    analysis['routine'].append({
                        'key': key,
                        'summary': summary
                    })
                
            except Exception as e:
                print(f"Warning: Error analyzing ticket: {e}")
                continue
        
        print(f"✓ Analyzed {len(tickets)} tickets")
        print(f"  - Needs discussion: {len(analysis['needs_discussion'])}")
        print(f"  - Routine: {len(analysis['routine'])}")
        print(f"  - Broken tickets: {len(analysis['broken_tickets'])}")
        print(f"  - Unanswered tickets: {len(analysis['unanswered_tickets'])}")
        
        return analysis
    
    def assess_discussion_need(self, key: str, summary: str, description: str, status: str, ticket_type: str) -> Dict[str, Any]:
        """
        Assess whether a ticket needs team discussion based on configured keywords.
        
        Returns: {
            'needs_discussion': bool,
            'reason': str,
            'priority': str  # 'High', 'Normal', 'Low'
        }
        """
        
        # Combine summary and description for analysis
        full_text = f"{summary} {description}".lower()
        
        # Load keywords from config
        analysis_config = self.config.get('analysis', {})
        routine_keywords = analysis_config.get('routine_keywords', ['cjib', 'export'])
        discussion_keywords = analysis_config.get('discussion_keywords', ['crash', 'bug', 'error'])
        critical_keywords = analysis_config.get('critical_keywords', ['crash', 'critical', 'urgent'])
        min_chars = analysis_config.get('min_chars_for_vague_check', 20)
        
        # Check if this is a routine issue (no discussion needed)
        if any(keyword in full_text for keyword in routine_keywords):
            return {
                'needs_discussion': False,
                'reason': 'Routine issue'
            }
        
        # Check if discussion is needed based on keywords
        if any(keyword in full_text for keyword in discussion_keywords):
            # Determine priority
            if any(keyword in full_text for keyword in critical_keywords):
                priority = 'High'
            else:
                priority = 'Normal'
            
            return {
                'needs_discussion': True,
                'reason': 'Potential bug or system issue requiring team review',
                'priority': priority
            }
        
        # Check for unclear/vague issues (indicate discussion needed)
        if len(full_text.strip()) < min_chars:
            return {
                'needs_discussion': True,
                'reason': 'Unclear problem statement - needs clarification',
                'priority': 'Normal'
            }
        
        # Default: needs discussion if we're not sure
        if status in ['Open', 'New', 'To Do', 'OPEN']:
            return {
                'needs_discussion': True,
                'reason': 'New open issue - awaiting team triage',
                'priority': 'Normal'
            }
        
        return {
            'needs_discussion': False,
            'reason': 'No discussion needed'
        }
    
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
        
        # Add tickets needing team discussion (HIGH PRIORITY)
        if analysis['needs_discussion']:
            discussion_text = "*🔴 NEEDS TEAM DISCUSSION:*\n"
            for ticket in analysis['needs_discussion']:
                priority_emoji = "🔴" if ticket.get('priority') == 'High' else "🟡"
                discussion_text += f"{priority_emoji} <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']}\n"
                discussion_text += f"   _Reason:_ {ticket['reason']}\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": discussion_text
                }
            })
        
        # Add routine tickets
        if analysis['routine']:
            routine_text = "*✅ Routine Issues (No Discussion Needed):*\n"
            for ticket in analysis['routine'][:5]:
                routine_text += f"• <{self.jira_url}/browse/{ticket['key']}|{ticket['key']}> - {ticket['summary']}\n"
            if len(analysis['routine']) > 5:
                routine_text += f"• ... and {len(analysis['routine']) - 5} more routine issues\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": routine_text
                }
            })
        
        # Add broken tickets section (if any)
        if analysis['broken_tickets']:
            broken_text = "*⚠️  Incomplete Tickets (Missing Details):*\n"
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
        
        # Add summary section
        summary_text = f"*Summary:* {len(analysis['needs_discussion'])} issues need discussion, {len(analysis['routine'])} are routine"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": summary_text
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
