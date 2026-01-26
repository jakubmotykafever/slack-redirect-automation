"""
N8N webhook client for triggering redirect workflows.
Sends redirect data to N8N for processing.
"""

import requests
from typing import Optional
from dataclasses import asdict

from .config import Config
from .slack_parser import RedirectRequest


class N8NClient:
    """
    Client for interacting with N8N webhooks.
    Sends redirect requests to trigger the redirect workflow.
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize the N8N client.
        
        Args:
            webhook_url: The N8N webhook URL. Defaults to config value.
        """
        self.webhook_url = webhook_url or Config.N8N_WEBHOOK_URL
        self.timeout = 30  # seconds
    
    def send_redirect(self, redirect: RedirectRequest) -> dict:
        """
        Send a single redirect request to N8N.
        
        Args:
            redirect: The RedirectRequest to send.
            
        Returns:
            Response data from N8N or error information.
        """
        payload = {
            'old_url': redirect.old_url,
            'new_url': redirect.new_url,
            'requester': redirect.requester,
            'reason': redirect.reason,
            'message_ts': redirect.message_ts
        }
        
        return self._send_request(payload)
    
    def send_batch(self, redirects: list[RedirectRequest]) -> dict:
        """
        Send a batch of redirect requests to N8N.
        
        Args:
            redirects: List of RedirectRequest objects to send.
            
        Returns:
            Response data from N8N or error information.
        """
        if not redirects:
            return {'success': True, 'message': 'No redirects to process'}
        
        # Convert to list of dictionaries
        payload = {
            'redirects': [
                {
                    'old_url': r.old_url,
                    'new_url': r.new_url,
                    'requester': r.requester,
                    'reason': r.reason,
                    'message_ts': r.message_ts
                }
                for r in redirects
            ],
            'count': len(redirects)
        }
        
        return self._send_request(payload)
    
    def send_batch_for_sheets(self, redirects: list[dict]) -> dict:
        """
        Send a batch of redirect dictionaries (from Sheets) to N8N.
        
        Args:
            redirects: List of redirect dictionaries from Sheets.
            
        Returns:
            Response data from N8N or error information.
        """
        if not redirects:
            return {'success': True, 'message': 'No redirects to process'}
        
        payload = {
            'redirects': [
                {
                    'old_url': r['old_url'],
                    'new_url': r['new_url'],
                    'requester': r.get('requester', ''),
                    'reason': r.get('reason', ''),
                }
                for r in redirects
            ],
            'count': len(redirects)
        }
        
        return self._send_request(payload)
    
    def _send_request(self, payload: dict) -> dict:
        """
        Send a request to the N8N webhook.
        
        Args:
            payload: The data to send.
            
        Returns:
            Response data or error information.
        """
        if not self.webhook_url:
            return {
                'success': False,
                'error': 'N8N webhook URL not configured'
            }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                data = response.json()
            except ValueError:
                data = {'raw_response': response.text}
            
            return {
                'success': True,
                'status_code': response.status_code,
                'data': data
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timed out',
                'timeout': self.timeout
            }
        except requests.exceptions.ConnectionError as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
        except requests.exceptions.HTTPError as e:
            return {
                'success': False,
                'error': f'HTTP error: {str(e)}',
                'status_code': e.response.status_code if e.response else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def test_connection(self) -> bool:
        """
        Test the connection to the N8N webhook.
        
        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            response = requests.head(
                self.webhook_url,
                timeout=5
            )
            # N8N webhooks might return 405 for HEAD, but at least we know it's reachable
            return response.status_code in [200, 405, 404]
        except Exception:
            return False
