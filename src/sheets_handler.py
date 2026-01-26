"""
Google Sheets handler for storing redirect requests.
Writes redirect URLs to a Google Sheet for tracking and N8N processing.
"""

import os
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import Config
from .slack_parser import RedirectRequest


class SheetsHandler:
    """
    Handler for Google Sheets operations.
    Manages writing redirect requests to a spreadsheet.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize the Sheets handler with credentials.
        
        Args:
            credentials_path: Path to the service account credentials JSON file.
        """
        self.credentials_path = credentials_path or Config.GOOGLE_CREDENTIALS_JSON
        self.spreadsheet_id = Config.GOOGLE_SHEETS_ID
        self.service = self._build_service()
    
    def _build_service(self):
        """Build the Google Sheets API service."""
        try:
            # Check if credentials is a JSON string or file path
            if os.path.exists(self.credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=self.SCOPES
                )
            else:
                # Try to parse as JSON string (for cloud deployment)
                import json
                creds_dict = json.loads(self.credentials_path)
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=self.SCOPES
                )
            
            return build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            print(f"Error building Sheets service: {e}")
            return None
    
    def write_redirects(
        self, 
        redirects: list[RedirectRequest], 
        sheet_name: str = "Redirects"
    ) -> bool:
        """
        Write redirect requests to the spreadsheet.
        
        Args:
            redirects: List of RedirectRequest objects to write.
            sheet_name: Name of the sheet within the spreadsheet.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self.service:
            print("Sheets service not available")
            return False
        
        if not redirects:
            print("No redirects to write")
            return True
        
        try:
            # Prepare the data rows
            rows = []
            for redirect in redirects:
                rows.append([
                    redirect.old_url,
                    redirect.new_url,
                    redirect.requester,
                    redirect.reason or "",
                    redirect.message_ts,
                    "pending"  # Status column
                ])
            
            # Append to the sheet
            body = {
                'values': rows
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:F",
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            updated_rows = result.get('updates', {}).get('updatedRows', 0)
            print(f"Successfully wrote {updated_rows} redirects to sheet")
            return True
            
        except HttpError as e:
            print(f"Error writing to sheet: {e}")
            return False
    
    def get_pending_redirects(self, sheet_name: str = "Redirects") -> list[dict]:
        """
        Get all pending redirects from the spreadsheet.
        
        Args:
            sheet_name: Name of the sheet within the spreadsheet.
            
        Returns:
            List of pending redirect dictionaries.
        """
        if not self.service:
            print("Sheets service not available")
            return []
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:F"
            ).execute()
            
            rows = result.get('values', [])
            pending = []
            
            for i, row in enumerate(rows[1:], start=2):  # Skip header row
                if len(row) >= 6 and row[5] == 'pending':
                    pending.append({
                        'row_index': i,
                        'old_url': row[0],
                        'new_url': row[1],
                        'requester': row[2],
                        'reason': row[3],
                        'message_ts': row[4],
                        'status': row[5]
                    })
            
            return pending
            
        except HttpError as e:
            print(f"Error reading from sheet: {e}")
            return []
    
    def update_status(
        self, 
        row_index: int, 
        status: str, 
        sheet_name: str = "Redirects"
    ) -> bool:
        """
        Update the status of a redirect in the spreadsheet.
        
        Args:
            row_index: The row number to update (1-indexed).
            status: The new status value.
            sheet_name: Name of the sheet within the spreadsheet.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self.service:
            print("Sheets service not available")
            return False
        
        try:
            body = {
                'values': [[status]]
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!F{row_index}",
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
            
        except HttpError as e:
            print(f"Error updating status: {e}")
            return False
    
    def ensure_sheet_exists(self, sheet_name: str = "Redirects") -> bool:
        """
        Ensure the sheet exists with proper headers.
        Creates it if it doesn't exist.
        
        Args:
            sheet_name: Name of the sheet to check/create.
            
        Returns:
            True if sheet exists or was created, False on error.
        """
        if not self.service:
            print("Sheets service not available")
            return False
        
        try:
            # Get spreadsheet metadata
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheets = spreadsheet.get('sheets', [])
            sheet_exists = any(
                s.get('properties', {}).get('title') == sheet_name 
                for s in sheets
            )
            
            if not sheet_exists:
                # Create the sheet
                request_body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': sheet_name
                            }
                        }
                    }]
                }
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=request_body
                ).execute()
                
                # Add headers
                headers = [['Old URL', 'New URL', 'Requester', 'Reason', 'Message TS', 'Status']]
                body = {'values': headers}
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1:F1",
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                print(f"Created sheet '{sheet_name}' with headers")
            
            return True
            
        except HttpError as e:
            print(f"Error ensuring sheet exists: {e}")
            return False
