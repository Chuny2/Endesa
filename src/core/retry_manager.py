#!/usr/bin/env python3
"""Simple retry management without objects."""

import time
from typing import Callable, Tuple, Optional, Dict
from collections import deque


class SimpleRetryProcessor:
    """Simple retry processor for immediate retries (normal mode)."""
    
    def __init__(self, processor_func: Callable, max_retries: int = 2, 
                 retry_delay: float = 1.0, progress_callback: Optional[Callable] = None):
        self.processor_func = processor_func
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.progress_callback = progress_callback
        self.retry_count = 0
    
    def process_with_retry(self, email: str, password: str, line_num: int, proxy: Optional[str] = None) -> Tuple[str, str]:
        """Process credential with immediate retry on ban."""
        retry_count = 0
        
        while retry_count <= self.max_retries:
            result, result_type = self.processor_func(email, password, line_num, proxy)
            
            if result_type == "BANNED" and retry_count < self.max_retries:
                retry_count += 1
                self.retry_count += 1  # Total retry stats
                
                if self.progress_callback:
                    self.progress_callback(f"🔄 Retry attempt {retry_count}/{self.max_retries + 1} for {email}")
                
                if self.retry_delay > 0:
                    time.sleep(self.retry_delay)
                continue
            else:
                # Final result
                if result_type == "BANNED" and retry_count > 0:
                    
                    if not result.startswith("BANNED:"):
                        result = f"BANNED: {result}"
                    # Keep result_type as "BANNED" so main logic can handle coloring
                return result, result_type
        
        return result, result_type


class VPNRetryQueue:
    """Simple VPN retry queue using basic tuples."""
    
    def __init__(self, max_retries: int = 3, progress_callback: Optional[Callable] = None):
        self.max_retries = max_retries
        self.progress_callback = progress_callback
        # Queue stores (email, password, line_num, retry_count) tuples
        self.retry_queue = deque()
        self.total_retries = 0
    
    def process_batch_with_queue(self, processor_func: Callable, new_credentials: list) -> list:
        """
        Process batch combining retry queue with new credentials.
        
        Args:
            processor_func: The original _attempt_credential function
            new_credentials: List of (email, password, line_num) tuples
            
        Returns:
            List of (result, result_type, email, line_num) tuples for final results
        """
        # Combine retries and new credentials
        batch_to_process = []
        
        # Add retries from queue first (priority)
        while self.retry_queue:
            email, password, line_num, retry_count = self.retry_queue.popleft()
            batch_to_process.append((email, password, line_num, retry_count))
        
        # Add new credentials (retry_count = 0)
        for email, password, line_num in new_credentials:
            batch_to_process.append((email, password, line_num, 0))
        
        # Process and separate final results from retries
        final_results = []
        
        for email, password, line_num, retry_count in batch_to_process:
            result, result_type = processor_func(email, password, line_num)
            
            if result_type == "BANNED" and retry_count < self.max_retries:
                # Queue for next batch
                self.retry_queue.append((email, password, line_num, retry_count + 1))
                self.total_retries += 1
                
                if self.progress_callback:
                    self.progress_callback(f"⏳ Queued {email} for retry {retry_count + 1}/{self.max_retries}")
            else:
                # Final result
                if result_type == "BANNED" and retry_count > 0:
                    # Don't add BANNED prefix if result already starts with BANNED
                    if not result.startswith("BANNED:"):
                        result = f"BANNED: {result}"
                    # Keep result_type as "BANNED" so main logic can handle coloring
                final_results.append((result, result_type, email, line_num))
        
        return final_results
    
    def has_pending_retries(self) -> bool:
        """Check if there are pending retries."""
        return len(self.retry_queue) > 0 