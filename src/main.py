"""
Main orchestrator for the Slack Redirect Automation.
Coordinates the flow: Slack -> Parse -> Sheets -> N8N -> Mark processed.
"""

import logging
from typing import Optional

from .config import Config
from .slack_parser import SlackParser, RedirectRequest
from .sheets_handler import SheetsHandler
from .n8n_client import N8NClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedirectAutomation:
    """
    Main automation class that orchestrates the redirect workflow.
    """
    
    def __init__(self):
        """Initialize the automation with all required components."""
        self.slack_parser = SlackParser()
        self.sheets_handler = SheetsHandler()
        self.n8n_client = N8NClient()
    
    def run(self) -> dict:
        """
        Execute the main automation workflow.
        
        Returns:
            Dictionary with execution results and statistics.
        """
        results = {
            'messages_processed': 0,
            'redirects_found': 0,
            'redirects_sent_to_n8n': 0,
            'errors': []
        }
        
        # Validate configuration
        missing_config = Config.validate()
        if missing_config:
            error_msg = f"Missing configuration: {', '.join(missing_config)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
        
        logger.info("Starting redirect automation...")
        
        # Step 1: Ensure sheet exists
        if not self.sheets_handler.ensure_sheet_exists():
            results['errors'].append("Failed to ensure sheet exists")
            return results
        
        # Step 2: Get unprocessed messages from Slack
        logger.info("Fetching unprocessed messages from Slack...")
        messages = self.slack_parser.get_unprocessed_messages()
        logger.info(f"Found {len(messages)} unprocessed messages")
        
        if not messages:
            logger.info("No unprocessed messages found")
            return results
        
        # Step 3: Parse each message and extract redirects
        all_redirects: list[RedirectRequest] = []
        message_redirects: dict[str, list[RedirectRequest]] = {}
        
        for message in messages:
            message_ts = message.get('ts', '')
            redirects = self.slack_parser.parse_message(message)
            
            if redirects:
                all_redirects.extend(redirects)
                message_redirects[message_ts] = redirects
                logger.info(f"Found {len(redirects)} redirect(s) in message {message_ts}")
            else:
                logger.warning(f"Could not parse redirects from message {message_ts}")
        
        results['messages_processed'] = len(messages)
        results['redirects_found'] = len(all_redirects)
        
        if not all_redirects:
            logger.info("No redirects found in messages")
            return results
        
        # Step 4: Write redirects to Google Sheets
        logger.info(f"Writing {len(all_redirects)} redirects to Google Sheets...")
        if not self.sheets_handler.write_redirects(all_redirects):
            results['errors'].append("Failed to write redirects to sheet")
            return results
        
        # Step 5: Send to N8N in batches
        logger.info("Sending redirects to N8N...")
        batch_size = Config.MAX_REDIRECTS_PER_BATCH
        
        for i in range(0, len(all_redirects), batch_size):
            batch = all_redirects[i:i + batch_size]
            response = self.n8n_client.send_batch(batch)
            
            if response.get('success'):
                results['redirects_sent_to_n8n'] += len(batch)
                logger.info(f"Successfully sent batch of {len(batch)} redirects to N8N")
            else:
                error_msg = f"Failed to send batch to N8N: {response.get('error')}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        # Step 6: Mark messages as processed in Slack
        logger.info("Marking messages as processed...")
        for message_ts in message_redirects.keys():
            if self.slack_parser.mark_as_processed(message_ts):
                logger.info(f"Marked message {message_ts} as processed")
            else:
                results['errors'].append(f"Failed to mark message {message_ts} as processed")
        
        logger.info(f"Automation complete. Processed {results['redirects_found']} redirects.")
        return results


def process_redirects() -> dict:
    """
    Entry point function for the automation.
    Can be called directly or used as a Cloud Function handler.
    
    Returns:
        Dictionary with execution results.
    """
    automation = RedirectAutomation()
    return automation.run()


# Cloud Function entry point
def cloud_function_handler(request) -> tuple:
    """
    Google Cloud Function HTTP handler.
    
    Args:
        request: The Flask request object.
        
    Returns:
        Tuple of (response_body, status_code).
    """
    import json
    
    try:
        results = process_redirects()
        
        if results['errors']:
            return json.dumps({
                'status': 'completed_with_errors',
                'results': results
            }), 207
        
        return json.dumps({
            'status': 'success',
            'results': results
        }), 200
        
    except Exception as e:
        logger.exception("Error in cloud function")
        return json.dumps({
            'status': 'error',
            'error': str(e)
        }), 500


# For local execution
if __name__ == "__main__":
    import json
    
    results = process_redirects()
    print(json.dumps(results, indent=2))
