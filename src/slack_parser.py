"""
Slack message parser for extracting redirect URLs.
Handles multiple message formats used by editors.
"""

import re
from dataclasses import dataclass
from typing import Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import Config


@dataclass
class RedirectRequest:
    """Represents a single redirect request."""
    old_url: str
    new_url: str
    message_ts: str  # Slack message timestamp (used as unique ID)
    channel_id: str
    requester: str
    reason: Optional[str] = None


class SlackParser:
    """
    Parser for extracting redirect URLs from Slack messages.
    Handles various formats used by editors.
    """
    
    # Regex patterns for URL extraction
    URL_PATTERN = r'https?://[^\s<>"\'\]\)]+[^\s<>"\'\]\)\.,;:!?]'
    
    # Patterns for detecting old URLs
    OLD_URL_PATTERNS = [
        r'(?:old|vieja|antigua|from|de|origen)s?\s*(?:ones?|urls?)?\s*[:\-]?\s*',
        r'(?:redirigir|redirect)\s+(?:desde|from)\s*[:\-]?\s*',
    ]
    
    # Patterns for detecting new URLs
    NEW_URL_PATTERNS = [
        r'(?:new|nueva|to|a|destino|hacia)\s*(?:ones?|urls?)?\s*[:\-]?\s*',
        r'(?:redirigir|redirect)\s+(?:a|to|hacia)\s*[:\-]?\s*',
    ]
    
    def __init__(self, client: Optional[WebClient] = None):
        """Initialize the parser with an optional Slack client."""
        self.client = client or WebClient(token=Config.SLACK_BOT_TOKEN)
    
    def get_unprocessed_messages(self, channel_id: Optional[str] = None) -> list[dict]:
        """
        Fetch messages from the channel that haven't been processed yet.
        A message is considered processed if it has the configured emoji reaction.
        """
        channel = channel_id or Config.SLACK_CHANNEL_ID
        unprocessed = []
        
        try:
            # Get recent messages from the channel
            result = self.client.conversations_history(
                channel=channel,
                limit=100  # Adjust as needed
            )
            
            messages = result.get("messages", [])
            
            for message in messages:
                # Skip bot messages and messages without text
                if message.get("subtype") == "bot_message" or not message.get("text"):
                    continue
                
                # Check if message has the processed emoji
                reactions = message.get("reactions", [])
                has_processed_emoji = any(
                    r.get("name") == Config.PROCESSED_EMOJI 
                    for r in reactions
                )
                
                if not has_processed_emoji:
                    # Check if message contains URLs (potential redirect request)
                    if re.search(self.URL_PATTERN, message.get("text", "")):
                        unprocessed.append(message)
            
            return unprocessed
            
        except SlackApiError as e:
            print(f"Error fetching messages: {e.response['error']}")
            return []
    
    def parse_message(self, message: dict) -> list[RedirectRequest]:
        """
        Parse a Slack message and extract redirect requests.
        Returns a list of RedirectRequest objects.
        """
        text = message.get("text", "")
        message_ts = message.get("ts", "")
        channel_id = message.get("channel", Config.SLACK_CHANNEL_ID)
        requester = message.get("user", "unknown")
        
        # Clean up Slack formatting (remove <url|text> format)
        text = self._clean_slack_text(text)
        
        # Extract reason if present
        reason = self._extract_reason(text)
        
        # Try different parsing strategies
        redirects = self._parse_labeled_format(text)
        
        if not redirects:
            redirects = self._parse_multi_old_urls(text)
        
        if not redirects:
            redirects = self._parse_sequential_urls(text)
        
        # Convert to RedirectRequest objects
        requests = []
        for old_url, new_url in redirects:
            requests.append(RedirectRequest(
                old_url=old_url,
                new_url=new_url,
                message_ts=message_ts,
                channel_id=channel_id,
                requester=requester,
                reason=reason
            ))
        
        return requests
    
    def _clean_slack_text(self, text: str) -> str:
        """Remove Slack-specific formatting from text."""
        # Convert <url|display> to just url
        text = re.sub(r'<(https?://[^|>]+)\|[^>]+>', r'\1', text)
        # Convert <url> to just url
        text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
        return text
    
    def _extract_reason(self, text: str) -> Optional[str]:
        """Extract the reason for redirect if provided."""
        reason_patterns = [
            r'(?:reason|raz[oó]n|motivo)\s*[:\-]?\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in reason_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _parse_labeled_format(self, text: str) -> list[tuple[str, str]]:
        """
        Parse messages with explicit old/new labels.
        Examples:
            Old: https://example.com/old
            New: https://example.com/new
        """
        redirects = []
        
        # Find all URLs in the text
        urls = re.findall(self.URL_PATTERN, text)
        if len(urls) < 2:
            return []
        
        # Build combined patterns
        old_pattern = '|'.join(self.OLD_URL_PATTERNS)
        new_pattern = '|'.join(self.NEW_URL_PATTERNS)
        
        # Check if text has labeled format
        has_old_label = re.search(old_pattern, text, re.IGNORECASE)
        has_new_label = re.search(new_pattern, text, re.IGNORECASE)
        
        if not (has_old_label and has_new_label):
            return []
        
        # Split by lines and process
        lines = text.split('\n')
        old_urls = []
        new_urls = []
        current_type = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line starts a new section
            if re.search(old_pattern, line, re.IGNORECASE):
                current_type = 'old'
            elif re.search(new_pattern, line, re.IGNORECASE):
                current_type = 'new'
            
            # Extract URLs from this line
            line_urls = re.findall(self.URL_PATTERN, line)
            
            if current_type == 'old':
                old_urls.extend(line_urls)
            elif current_type == 'new':
                new_urls.extend(line_urls)
        
        # Create redirect pairs
        if old_urls and new_urls:
            # If multiple old URLs go to one new URL
            if len(new_urls) == 1:
                for old_url in old_urls:
                    redirects.append((old_url, new_urls[0]))
            # If same number of old and new URLs (1:1 mapping)
            elif len(old_urls) == len(new_urls):
                for old_url, new_url in zip(old_urls, new_urls):
                    redirects.append((old_url, new_url))
            # Otherwise, assume sequential pairing
            else:
                for i, old_url in enumerate(old_urls):
                    if i < len(new_urls):
                        redirects.append((old_url, new_urls[i]))
        
        return redirects
    
    def _parse_multi_old_urls(self, text: str) -> list[tuple[str, str]]:
        """
        Parse messages with multiple old URLs redirecting to one new URL.
        The new URL is typically the last one mentioned.
        """
        redirects = []
        
        # Look for patterns like "Old ones:" followed by URLs, then "New:" with one URL
        old_section_pattern = r'(?:old|vieja|antigua)s?\s*(?:ones?|urls?)?\s*[:\-](.+?)(?:new|nueva|to|a|destino)'
        
        match = re.search(old_section_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            old_section = match.group(1)
            old_urls = re.findall(self.URL_PATTERN, old_section)
            
            # Find the new URL (after the old section)
            remaining_text = text[match.end():]
            new_urls = re.findall(self.URL_PATTERN, remaining_text)
            
            if old_urls and new_urls:
                new_url = new_urls[0]  # Take the first URL after "New:"
                for old_url in old_urls:
                    redirects.append((old_url, new_url))
        
        return redirects
    
    def _parse_sequential_urls(self, text: str) -> list[tuple[str, str]]:
        """
        Parse messages where URLs are listed sequentially without clear labels.
        Assumes pairs of URLs where first is old, second is new.
        """
        redirects = []
        
        urls = re.findall(self.URL_PATTERN, text)
        
        # Need at least 2 URLs
        if len(urls) < 2:
            return []
        
        # If exactly 2 URLs, assume first is old, second is new
        if len(urls) == 2:
            # Verify they're from the same domain (likely a redirect)
            if self._same_domain(urls[0], urls[1]):
                redirects.append((urls[0], urls[1]))
        
        return redirects
    
    def _same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same domain."""
        try:
            from urllib.parse import urlparse
            domain1 = urlparse(url1).netloc
            domain2 = urlparse(url2).netloc
            return domain1 == domain2
        except Exception:
            return False
    
    def mark_as_processed(self, message_ts: str, channel_id: Optional[str] = None) -> bool:
        """
        Mark a message as processed by adding the configured emoji reaction.
        """
        channel = channel_id or Config.SLACK_CHANNEL_ID
        
        try:
            self.client.reactions_add(
                channel=channel,
                name=Config.PROCESSED_EMOJI,
                timestamp=message_ts
            )
            return True
        except SlackApiError as e:
            # Ignore if reaction already exists
            if e.response["error"] == "already_reacted":
                return True
            print(f"Error adding reaction: {e.response['error']}")
            return False
