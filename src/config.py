"""
Configuration module for Slack Redirect Automation.
Loads environment variables and provides configuration constants.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class with all required settings."""
    
    # Slack settings
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL_ID: str = os.getenv("SLACK_CHANNEL_ID", "")
    
    # Google Sheets settings
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "credentials.json")
    
    # N8N settings
    N8N_WEBHOOK_URL: str = os.getenv("N8N_WEBHOOK_URL", "")
    
    # Processing settings
    PROCESSED_EMOJI: str = os.getenv("PROCESSED_EMOJI", "white_check_mark")
    MAX_REDIRECTS_PER_BATCH: int = 5  # Maximum redirects per N8N execution
    
    @classmethod
    def validate(cls) -> list[str]:
        """
        Validate that all required configuration is present.
        Returns a list of missing configuration keys.
        """
        missing = []
        
        if not cls.SLACK_BOT_TOKEN:
            missing.append("SLACK_BOT_TOKEN")
        if not cls.SLACK_CHANNEL_ID:
            missing.append("SLACK_CHANNEL_ID")
        if not cls.GOOGLE_SHEETS_ID:
            missing.append("GOOGLE_SHEETS_ID")
        if not cls.N8N_WEBHOOK_URL:
            missing.append("N8N_WEBHOOK_URL")
            
        return missing
    
    @classmethod
    def is_valid(cls) -> bool:
        """Check if all required configuration is present."""
        return len(cls.validate()) == 0
