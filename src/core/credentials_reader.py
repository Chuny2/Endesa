#!/usr/bin/env python3
"""Memory-efficient credentials file reader."""

import os
from typing import Generator, List, Tuple


class CredentialsReader:
    """Memory-efficient credentials file reader that processes files in chunks."""
    
    def __init__(self, file_path: str, chunk_size: int = 1000):
        """
        Initialize the credentials reader.
        
        Args:
            file_path: Path to the credentials file
            chunk_size: Number of credentials to process in each chunk
        """
        self.file_path = file_path
        self.chunk_size = chunk_size
    
    def get_total_count(self) -> int:
        """
        Get the total number of valid credentials in the file.
        This scans the file once to count valid lines.
        """
        if not os.path.exists(self.file_path):
            return 0
        
        count = 0
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        count += 1
        except Exception:
            return 0
        
        return count
    
    def read_chunks(self) -> Generator[List[Tuple[str, str, int]], None, None]:
        """
        Generator that yields chunks of credentials from the file.
        
        Yields:
            List of tuples: (email, password, line_number)
        """
        if not os.path.exists(self.file_path):
            return
        
        chunk = []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and ':' in line:
                        email, password = line.split(':', 1)
                        chunk.append((email.strip(), password.strip(), line_num))
                        
                        # Yield chunk when it reaches the specified size
                        if len(chunk) >= self.chunk_size:
                            yield chunk
                            chunk = []
                    elif line:  # Line exists but no colon - this will be handled by caller
                        # We need to yield invalid lines too for proper error reporting
                        chunk.append(("INVALID_LINE", line, line_num))
                        
                        if len(chunk) >= self.chunk_size:
                            yield chunk
                            chunk = []
            
            # Yield any remaining credentials in the final chunk
            if chunk:
                yield chunk
                
        except Exception as e:
            # If there's an error reading the file, yield an empty chunk
            # The caller will handle the file reading error
            if chunk:
                yield chunk
    
    def read_all_credentials(self) -> List[Tuple[str, str, int]]:
        """
        Read all credentials at once (for backward compatibility).
        This method maintains the original behavior but is less memory efficient.
        """
        all_credentials = []
        for chunk in self.read_chunks():
            all_credentials.extend(chunk)
        return all_credentials 