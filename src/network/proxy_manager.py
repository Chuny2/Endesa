#!/usr/bin/env python3
"""Proxy management system for Endesa batch processing."""

import random
import time
import requests
from typing import List, Optional, Dict, Tuple
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from PyQt6.QtCore import QObject, pyqtSignal


class ProxyManager(QObject):
    """Manages proxy rotation, validation, and health monitoring."""
    
    # Signal emitted when a proxy is automatically removed
    proxy_removed = pyqtSignal(str, str)  # (proxy, reason)
    
    def __init__(self, proxy_list: Optional[List[str]] = None, 
                 timeout: int = 3, auto_remove_failed: bool = True):
        """
        Initialize the proxy manager.
        
        Args:
            proxy_list: List of proxy URLs (format: protocol://ip:port or protocol://user:pass@ip:port)
            timeout: Timeout for proxy validation requests
            auto_remove_failed: Automatically remove proxies that fail repeatedly
        """
        super().__init__()  # Initialize QObject
        self.proxy_list = proxy_list or []
        self.timeout = timeout
        self.auto_remove_failed = auto_remove_failed  # Auto-remove failed proxies
        self.proxy_health: Dict[str, Dict] = {}
        self.test_urls = [
            "http://httpbin.org/ip",
            "https://api.ipify.org?format=json",
            "http://icanhazip.com"
        ]
        
        # Initialize proxy health tracking
        self._initialize_proxy_health()
        
    def _initialize_proxy_health(self):
        """Initialize health tracking for all proxies."""
        for proxy in self.proxy_list:
            self.proxy_health[proxy] = {
                'failures': 0,
                'successes': 0,
                'last_used': 0,
                'response_time': 0,
                'is_healthy': False,  # Start as unhealthy until tested
                'status': 'untested'  # Track actual status: untested, healthy, unhealthy
            }
    
    def add_proxy(self, proxy: str) -> bool:
        """
        Add a new proxy to the list.
        
        Args:
            proxy: Proxy URL string
            
        Returns:
            bool: True if proxy was added successfully
        """
        if proxy and proxy not in self.proxy_list:
            if self._validate_proxy_format(proxy):
                self.proxy_list.append(proxy)
                self.proxy_health[proxy] = {
                    'failures': 0,
                    'successes': 0,
                    'last_used': 0,
                    'response_time': 0,
                    'is_healthy': False,  # Start as unhealthy until tested
                    'status': 'untested'  # Track actual status: untested, healthy, unhealthy
                }
                return True
        return False
    
    def remove_proxy(self, proxy: str) -> bool:
        """
        Remove a proxy from the list.
        
        Args:
            proxy: Proxy URL string
            
        Returns:
            bool: True if proxy was removed successfully
        """
        if proxy in self.proxy_list:
            self.proxy_list.remove(proxy)
            if proxy in self.proxy_health:
                del self.proxy_health[proxy]
            return True
        return False
    
    def _validate_proxy_format(self, proxy: str) -> bool:
        """
        Validate proxy URL format. Supports multiple formats:
        - http://host:port
        - http://user:pass@host:port
        - socks5://host:port
        - IP:PORT
        - IP:PORT:USER:PASS
        - IP:PORT:USERNAME__DOMAIN:PASSWORD
        - USER:PASS@IP:PORT
        """
        if not proxy or not proxy.strip():
            return False
            
        proxy = proxy.strip()
        
        try:
            # Full URL with scheme
            if '://' in proxy:
                parsed = urlparse(proxy)
                return bool(parsed.scheme and parsed.hostname and parsed.port)
            
            # USER:PASS@IP:PORT format
            elif '@' in proxy:
                auth_part, server_part = proxy.split('@', 1)
                # Validate auth part
                if ':' not in auth_part:
                    return False
                # Validate server part
                if ':' not in server_part:
                    return False
                parts = server_part.split(':')
                if len(parts) != 2:
                    return False
                host, port = parts
                return bool(host.strip() and port.strip().isdigit() and 1 <= int(port) <= 65535)
            
            # IP:PORT:USER:PASS format
            elif proxy.count(':') >= 3:
                parts = proxy.split(':')
                if len(parts) < 4:
                    return False
                host, port = parts[0], parts[1]
                # Check if host and port are valid
                if not host.strip() or not port.strip().isdigit():
                    return False
                port_num = int(port)
                return 1 <= port_num <= 65535
            
            # Format 4: Simple IP:PORT or HOST:PORT
            elif proxy.count(':') == 1:
                parts = proxy.split(':')
                if len(parts) != 2:
                    return False
                host, port = parts
                if not host.strip() or not port.strip().isdigit():
                    return False
                port_num = int(port)
                return 1 <= port_num <= 65535
            
            else:
                return False
                
        except (ValueError, AttributeError) as e:
            return False
    
    def get_next_proxy(self) -> Optional[str]:
        """
        Get the next healthy proxy in rotation.
        
        Returns:
            str: Next proxy URL or None if no healthy proxies available
        """
        if not self.proxy_list:
            return None
        
        healthy_proxies = [p for p in self.proxy_list if self.proxy_health[p]['is_healthy']]
        
        if not healthy_proxies:
            # No healthy proxies, reset all to healthy and try again
            self._reset_proxy_health()
            healthy_proxies = self.proxy_list
        
        if not healthy_proxies:
            return None
        
        # Use round-robin with preference for least recently used
        healthy_proxies.sort(key=lambda p: self.proxy_health[p]['last_used'])
        
        proxy = healthy_proxies[0]
        self.proxy_health[proxy]['last_used'] = time.time()
        
        return proxy
    
    def _normalize_proxy_for_requests(self, proxy: str) -> str:
        """
        Convert various proxy formats to the format expected by requests library.
        
        Args:
            proxy: Proxy string in various formats
            
        Returns:
            str: Normalized proxy URL for requests library
        """
        if not proxy:
            return proxy
            
        proxy = proxy.strip()
        
        # Already in URL format
        if '://' in proxy:
            return proxy
        
        # Format: USER:PASS@IP:PORT
        if '@' in proxy:
            return f"http://{proxy}"
        
        # Format: IP:PORT:USER:PASS or IP:PORT:USERNAME__DOMAIN:PASSWORD
        elif proxy.count(':') >= 3:
            parts = proxy.split(':')
            host, port = parts[0], parts[1]
            # Join all remaining parts as username:password (handles domain cases)
            auth = ':'.join(parts[2:])
            return f"http://{auth}@{host}:{port}"
        
        # Format: IP:PORT
        elif proxy.count(':') == 1:
            return f"http://{proxy}"
        
        else:
            # Fallback - assume it's already in correct format
            return proxy
    
    def get_random_proxy(self) -> Optional[str]:
        """
        Get a random healthy proxy.
        
        Returns:
            str: Random proxy URL or None if no healthy proxies available
        """
        if not self.proxy_list:
            return None
        
        healthy_proxies = [p for p in self.proxy_list if self.proxy_health[p]['is_healthy']]
        
        if not healthy_proxies:
            # No healthy proxies, reset all to healthy and try again
            self._reset_proxy_health()
            healthy_proxies = self.proxy_list
        
        if not healthy_proxies:
            return None
        
        proxy = random.choice(healthy_proxies)
        self.proxy_health[proxy]['last_used'] = time.time()
        
        return proxy
    
    def get_best_proxy(self) -> Optional[str]:
        """
        Get the proxy with best performance (lowest response time and highest success rate).
        
        Returns:
            str: Best performing proxy URL or None if no proxies available
        """
        if not self.proxy_list:
            return None
        
        healthy_proxies = [p for p in self.proxy_list if self.proxy_health[p]['is_healthy']]
        
        if not healthy_proxies:
            self._reset_proxy_health()
            healthy_proxies = self.proxy_list
        
        if not healthy_proxies:
            return None
        
        # Score based on success rate and response time
        def calculate_score(proxy):
            health = self.proxy_health[proxy]
            total_requests = health['successes'] + health['failures']
            if total_requests == 0:
                success_rate = 0.5  # Neutral score for untested proxies
            else:
                success_rate = health['successes'] / total_requests
            
            # Lower response time is better, so invert it
            response_score = 1.0 / (health['response_time'] + 0.1)  # Add small value to avoid division by zero
            
            return success_rate * 0.7 + response_score * 0.3
        
        best_proxy = max(healthy_proxies, key=calculate_score)
        self.proxy_health[best_proxy]['last_used'] = time.time()
        
        return best_proxy
    
    def test_proxy(self, proxy: str, test_url: Optional[str] = None) -> Tuple[bool, float]:
        """
        Test if a proxy is working.
        
        Args:
            proxy: Proxy URL to test
            test_url: URL to test against (uses default if None)
            
        Returns:
            tuple: (is_working, response_time)
        """
        if test_url is None:
            test_url = random.choice(self.test_urls)
        
        # Normalize proxy format for requests library
        normalized_proxy = self._normalize_proxy_for_requests(proxy)
        
        proxy_dict = {
            'http': normalized_proxy,
            'https': normalized_proxy
        }
        
        start_time = time.time()
        try:
            response = requests.get(test_url, proxies=proxy_dict, timeout=self.timeout)
            response_time = time.time() - start_time
            
            # Record result
            if response.status_code == 200:
                self._record_success(proxy, response_time)
                return True, response_time
            else:
                self._record_failure(proxy)
                return False, response_time
                
        except Exception:
            response_time = time.time() - start_time
            self._record_failure(proxy)
            return False, response_time
    
    def test_all_proxies(self, progress_callback=None) -> Dict[str, Tuple[bool, float]]:
        """
        Test all proxies in the list using high-performance parallel testing.
        
        Returns:
            dict: Mapping of proxy -> (is_working, response_time)
        """
        results = {}
        
        if not self.proxy_list:
            return results
        
        # Configure batching based on dataset size
        total_proxies = len(self.proxy_list)
        
        if total_proxies <= 100:
            batch_size = 25
            max_workers = 10
            batch_delay = 0.01
        elif total_proxies <= 500:
            batch_size = 50
            max_workers = 15
            batch_delay = 0.02
        elif total_proxies <= 2000:
            batch_size = 100
            max_workers = 20
            batch_delay = 0.05
        else:
            batch_size = 200
            max_workers = 25
            batch_delay = 0.1
        
        completed = 0
        
        # Process proxies in batches
        for i in range(0, total_proxies, batch_size):
            batch = self.proxy_list[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._test_proxy_ultra_fast, proxy): proxy 
                    for proxy in batch
                }
                
                # Collect batch results
                for future in as_completed(futures, timeout=10):
                    proxy = futures[future]
                    try:
                        is_working, response_time = future.result(timeout=0.5)
                        results[proxy] = (is_working, response_time)
                        completed += 1
                        
                        # Progress callbacks
                        if progress_callback and total_proxies > 1000:
                            if completed % 100 == 0 or completed == total_proxies:
                                progress_callback(completed, total_proxies)
                        elif progress_callback and (completed % 20 == 0 or completed == total_proxies):
                            progress_callback(completed, total_proxies)
                            
                    except Exception:
                        results[proxy] = (False, 0.0)
                        completed += 1
            
            # Delay between batches
            if batch_delay > 0:
                time.sleep(batch_delay)
        
        return results
    
    def _test_proxy_ultra_fast(self, proxy: str):
        """Ultra-fast proxy testing with minimal overhead."""
        try:
            normalized_proxy = self._normalize_proxy_for_requests(proxy)
            proxy_dict = {'http': normalized_proxy, 'https': normalized_proxy}
            
            start_time = time.time()
            response = requests.get(
                "http://httpbin.org/ip",
                proxies=proxy_dict, 
                timeout=1.5,
                headers={'User-Agent': 'FastTest/1.0'},
                allow_redirects=False
            )
            response_time = time.time() - start_time
            
            # Record result
            if response.status_code == 200:
                self._record_success(proxy, response_time)
                return True, response_time
            else:
                self._record_failure(proxy)
                return False, response_time
                
        except Exception:
            self._record_failure(proxy)
            return False, 0.0
    

    
    def _record_success(self, proxy: str, response_time: float):
        """Record a successful proxy usage."""
        if proxy in self.proxy_health:
            self.proxy_health[proxy]['successes'] += 1
            self.proxy_health[proxy]['response_time'] = response_time
            self.proxy_health[proxy]['failures'] = 0  # Reset failure counter
            self.proxy_health[proxy]['is_healthy'] = True
            self.proxy_health[proxy]['status'] = 'healthy'
    
    def _record_failure(self, proxy: str):
        """Record a failed proxy usage with immediate removal if enabled."""
        if proxy in self.proxy_health:
            self.proxy_health[proxy]['failures'] += 1
            self.proxy_health[proxy]['status'] = 'unhealthy'
            self.proxy_health[proxy]['is_healthy'] = False
            
            # Remove immediately when marked as unhealthy (if auto-removal enabled)
            if self.auto_remove_failed:
                self._remove_proxy_automatically(proxy)
    
    def _remove_proxy_automatically(self, proxy: str):
        """Remove a proxy that has failed too many times."""
        try:
            if proxy in self.proxy_list:
                # Remove from proxy list
                self.proxy_list.remove(proxy)
                
                # Remove from health tracking
                if proxy in self.proxy_health:
                    del self.proxy_health[proxy]
                
                # Emit signal for UI notification
                reason = f"Failed testing"
                self.proxy_removed.emit(proxy, reason)
                
                print(f"🗑️ Auto-removed unhealthy proxy: {proxy} ({reason})")
                
        except Exception as e:
            print(f"Error removing proxy {proxy}: {e}")
    
    def mark_proxy_failed(self, proxy: str):
        """Manually mark a proxy as failed (called from external code)."""
        self._record_failure(proxy)
    
    def mark_proxy_success(self, proxy: str, response_time: float = 0):
        """Manually mark a proxy as successful (called from external code)."""
        self._record_success(proxy, response_time)
    
    def _reset_proxy_health(self):
        """Reset all proxies to untested status (thread-safe)."""
        try:
            # Create list copy to avoid race conditions during iteration
            proxy_keys = list(self.proxy_health.keys())
            for proxy in proxy_keys:
                if proxy in self.proxy_health:  # Double-check in case removed during iteration
                    self.proxy_health[proxy]['is_healthy'] = False
                    self.proxy_health[proxy]['failures'] = 0
                    self.proxy_health[proxy]['status'] = 'untested'
        except Exception as e:
            print(f"Error resetting proxy health: {e}")
    
    def get_proxy_stats(self) -> Dict[str, Dict]:
        """
        Get detailed statistics for all proxies.
        
        Returns:
            dict: Proxy statistics
        """
        return self.proxy_health.copy()
    
    def get_healthy_proxy_count(self) -> int:
        """Get the number of healthy proxies (thread-safe)."""
        try:
            # Create a snapshot to avoid race conditions during iteration
            health_snapshot = dict(self.proxy_health)
            return sum(1 for health in health_snapshot.values() if health['is_healthy'])
        except Exception:
            # Count healthy proxies directly
            return sum(1 for proxy in list(self.proxy_list) 
                      if self.proxy_health.get(proxy, {}).get('is_healthy', False))
    
    def load_proxies_from_file(self, file_path: str) -> int:
        """
        Load proxies from a text file (one proxy per line).
        
        Args:
            file_path: Path to the proxy file
            
        Returns:
            int: Number of proxies loaded
        """
        loaded_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    proxy = line.strip()
                    if proxy and not proxy.startswith('#'):  # Skip comments
                        if self.add_proxy(proxy):
                            loaded_count += 1
        except Exception as e:
            logging.error(f"Failed to load proxies from file {file_path}: {e}")
        
        return loaded_count
    
    def save_proxies_to_file(self, file_path: str) -> bool:
        """
        Save current proxy list to a text file.
        
        Args:
            file_path: Path where to save the proxies
            
        Returns:
            bool: True if saved successfully
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for proxy in self.proxy_list:
                    f.write(f"{proxy}\n")
            return True
        except Exception as e:
            logging.error(f"Failed to save proxies to file {file_path}: {e}")
            return False
    
    def clear_proxies(self):
        """Clear all proxies from the list."""
        self.proxy_list.clear()
        self.proxy_health.clear()
    
 