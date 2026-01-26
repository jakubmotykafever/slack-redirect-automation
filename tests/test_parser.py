"""
Unit tests for the Slack message parser.
Tests various message formats that editors use for redirect requests.
"""

import pytest
from unittest.mock import MagicMock, patch

# Mock the config before importing the parser
with patch.dict('os.environ', {
    'SLACK_BOT_TOKEN': 'test-token',
    'SLACK_CHANNEL_ID': 'test-channel',
    'GOOGLE_SHEETS_ID': 'test-sheet',
    'N8N_WEBHOOK_URL': 'https://test.n8n.com/webhook'
}):
    import sys
    sys.path.insert(0, '..')
    from src.slack_parser import SlackParser, RedirectRequest


class TestSlackParser:
    """Tests for the SlackParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance with mocked Slack client."""
        with patch('src.slack_parser.WebClient'):
            return SlackParser()
    
    def test_parse_old_new_format(self, parser):
        """Test parsing messages with Old/New format."""
        message = {
            'text': '''Hi guys!
Redirect please :)
Old: https://secretmanchester.com/snow-greater-manchester-january-2026/
New: https://secretmanchester.com/greater-manchester-snow-rain-storm-chandra-january/
Reason: Discover
Thanks''',
            'ts': '1234567890.123456',
            'user': 'U12345'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 1
        assert redirects[0].old_url == 'https://secretmanchester.com/snow-greater-manchester-january-2026/'
        assert redirects[0].new_url == 'https://secretmanchester.com/greater-manchester-snow-rain-storm-chandra-january/'
        assert redirects[0].reason == 'Discover'
    
    def test_parse_from_to_format(self, parser):
        """Test parsing messages with from/to format."""
        message = {
            'text': '''helloo!
redirect, pls?
from: https://saopaulosecreto.com/salesopolis/
to: https://saopaulosecreto.com/o-que-fazer-em-salesopolis-nascente-rio-tiete-sao-paulo/
reason: dead article; topic is trending on Discover monitoring
thankss''',
            'ts': '1234567890.123457',
            'user': 'U12346'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 1
        assert redirects[0].old_url == 'https://saopaulosecreto.com/salesopolis/'
        assert redirects[0].new_url == 'https://saopaulosecreto.com/o-que-fazer-em-salesopolis-nascente-rio-tiete-sao-paulo/'
    
    def test_parse_multiple_old_urls(self, parser):
        """Test parsing messages with multiple old URLs to one new URL."""
        message = {
            'text': '''Hi, could I get the following urls redirected please?
Old ones: https://marseillesecrete.com/cezanne-kandinsky-la-nouvelle-expo-immersive-a-voir-aux-carrieres-de-lumieres-en-2021/
https://marseillesecrete.com/exposition-carrieres-des-lumieres/
https://marseillesecrete.com/dali-et-gaudi-debarquent-aux-carrieres-de-lumieres-pour-une-experience-immersive-inedite/
https://marseillesecrete.com/provence-le-prochain-grand-defile-chanel-aura-lieu-aux-carrieres-de-lumieres/
New: https://marseillesecrete.com/carrieres-des-lumieres-expositions-picasso-frida-kahlo/
Reason: old articles for past exhibitions, updated info, GD potential''',
            'ts': '1234567890.123458',
            'user': 'U12347'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 4
        
        # All should point to the same new URL
        new_url = 'https://marseillesecrete.com/carrieres-des-lumieres-expositions-picasso-frida-kahlo/'
        for redirect in redirects:
            assert redirect.new_url == new_url
        
        # Check old URLs
        old_urls = [r.old_url for r in redirects]
        assert 'https://marseillesecrete.com/cezanne-kandinsky-la-nouvelle-expo-immersive-a-voir-aux-carrieres-de-lumieres-en-2021/' in old_urls
        assert 'https://marseillesecrete.com/exposition-carrieres-des-lumieres/' in old_urls
    
    def test_parse_simple_two_urls(self, parser):
        """Test parsing messages with just two URLs (same domain)."""
        message = {
            'text': '''Hi, can I get a redirect please?
Old: https://secretmanchester.com/six-nations-fan-zone-manchester/
New: https://secretmanchester.com/six-nations-fan-zone-freight-island-manchester/
Reason: New info for this year, Discover
Thanks!''',
            'ts': '1234567890.123459',
            'user': 'U12348'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 1
        assert redirects[0].old_url == 'https://secretmanchester.com/six-nations-fan-zone-manchester/'
        assert redirects[0].new_url == 'https://secretmanchester.com/six-nations-fan-zone-freight-island-manchester/'
    
    def test_clean_slack_text_with_brackets(self, parser):
        """Test that Slack URL formatting is properly cleaned."""
        # Slack formats URLs like <url|display_text> or <url>
        text = '<https://example.com/old|Click here>'
        cleaned = parser._clean_slack_text(text)
        
        assert cleaned == 'https://example.com/old'
    
    def test_clean_slack_text_simple_brackets(self, parser):
        """Test cleaning simple bracketed URLs."""
        text = '<https://example.com/page>'
        cleaned = parser._clean_slack_text(text)
        
        assert cleaned == 'https://example.com/page'
    
    def test_extract_reason(self, parser):
        """Test extracting reason from message text."""
        text = '''Some redirect request
Reason: This is the reason for the redirect
Thanks!'''
        
        reason = parser._extract_reason(text)
        
        assert reason == 'This is the reason for the redirect'
    
    def test_same_domain_check(self, parser):
        """Test the same domain verification."""
        url1 = 'https://example.com/old-page'
        url2 = 'https://example.com/new-page'
        url3 = 'https://other.com/page'
        
        assert parser._same_domain(url1, url2) is True
        assert parser._same_domain(url1, url3) is False
    
    def test_message_without_urls(self, parser):
        """Test that messages without URLs return empty list."""
        message = {
            'text': 'Hello, this is just a regular message without URLs.',
            'ts': '1234567890.123460',
            'user': 'U12349'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 0
    
    def test_message_with_single_url(self, parser):
        """Test that messages with only one URL return empty list."""
        message = {
            'text': 'Check out this link: https://example.com/page',
            'ts': '1234567890.123461',
            'user': 'U12350'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 0
    
    def test_redirect_request_dataclass(self):
        """Test the RedirectRequest dataclass."""
        redirect = RedirectRequest(
            old_url='https://example.com/old',
            new_url='https://example.com/new',
            message_ts='1234567890.123456',
            channel_id='C12345',
            requester='U12345',
            reason='Test reason'
        )
        
        assert redirect.old_url == 'https://example.com/old'
        assert redirect.new_url == 'https://example.com/new'
        assert redirect.reason == 'Test reason'


class TestSlackParserEdgeCases:
    """Edge case tests for the parser."""
    
    @pytest.fixture
    def parser(self):
        """Create a parser instance with mocked Slack client."""
        with patch('src.slack_parser.WebClient'):
            return SlackParser()
    
    def test_urls_without_trailing_slash(self, parser):
        """Test parsing URLs without trailing slashes."""
        message = {
            'text': '''Old: https://example.com/old-page
New: https://example.com/new-page''',
            'ts': '1234567890.123462',
            'user': 'U12351'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 1
        assert redirects[0].old_url == 'https://example.com/old-page'
    
    def test_mixed_case_labels(self, parser):
        """Test parsing with mixed case labels (OLD, New, FROM, etc.)."""
        message = {
            'text': '''OLD: https://example.com/old
NEW: https://example.com/new''',
            'ts': '1234567890.123463',
            'user': 'U12352'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 1
    
    def test_spanish_labels(self, parser):
        """Test parsing with Spanish labels (vieja, nueva)."""
        message = {
            'text': '''Vieja: https://example.com/antigua
Nueva: https://example.com/nueva''',
            'ts': '1234567890.123464',
            'user': 'U12353'
        }
        
        redirects = parser.parse_message(message)
        
        assert len(redirects) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
