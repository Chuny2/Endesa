#!/usr/bin/env python3
"""Session pool for efficient HTTP session management."""

import queue
import threading
import time
from typing import Optional

import requests


class SessionPool:
    """Thread-safe pool of HTTP sessions for efficient reuse."""
    
    def __init__(self, pool_size: int = 20, max_workers: int = 200):
        """
        Initialize session pool.
        
        Args:
            pool_size: Number of sessions to pre-create and maintain
            max_workers: Maximum number of worker threads (for connection pool sizing)
        """
        self.pool = queue.Queue(maxsize=pool_size)
        self.pool_size = pool_size
        self.max_workers = max_workers
        self.lock = threading.Lock()
        self.created_sessions = 0
        self.max_overflow = pool_size // 2  # Allow some overflow sessions
        
        # Pre-create sessions
        for _ in range(pool_size):
            session = self._create_optimized_session()
            self.pool.put(session)
            self.created_sessions += 1
    
    def _create_optimized_session(self) -> requests.Session:
        """Create an optimized session with proper connection pooling."""
        session = requests.Session()
        
        # Configure headers (same as original EndesaClient)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
            'Accept': 'text/plain, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # Optimized connection pool sizing for shared sessions
        # Since sessions are shared, we need larger pools per session
        connections_per_host = max(25, self.max_workers // 4)  # More aggressive pooling
        
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,    # Handle more different hosts
            pool_maxsize=connections_per_host,  # Larger pool per host
            max_retries=1
        )
        
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def get_session(self) -> requests.Session:
        """
        Get a session from the pool.
        
        Returns:
            A clean session ready for use
        """
        try:
            # Try to get session from pool
            session = self.pool.get_nowait()
        except queue.Empty:
            # Pool empty, create overflow session if allowed
            with self.lock:
                if self.created_sessions < self.pool_size + self.max_overflow:
                    session = self._create_optimized_session()
                    self.created_sessions += 1
                else:
                    # Wait for a session to become available
                    session = self.pool.get(timeout=30)
        
        # CRITICAL: Clear any previous user's authentication state
        session.cookies.clear()
        session.proxies.clear()  # Clear any previous proxy settings
        
        return session
    
    def return_session(self, session: requests.Session, had_error: bool = False):
        """
        Return a session to the pool.
        
        Args:
            session: The session to return
            had_error: Whether the session encountered an error
        """
        if had_error:
            # Don't return potentially corrupted sessions to pool
            try:
                session.close()
            except:
                pass
            return
        
        # Clean session state before returning to pool
        session.cookies.clear()
        session.proxies.clear()
        
        # Try to return to pool
        try:
            self.pool.put_nowait(session)
        except queue.Full:
            # Pool is full, close excess session
            try:
                session.close()
            except:
                pass
    
    def close_all(self):
        """Close all sessions in the pool."""
        while not self.pool.empty():
            try:
                session = self.pool.get_nowait()
                session.close()
            except queue.Empty:
                break
            except:
                pass


class SessionPoolManager:
    """Context manager for safe session pool usage."""
    
    def __init__(self, session_pool: SessionPool):
        self.session_pool = session_pool
        self.session = None
        self.had_error = False
    
    def __enter__(self) -> requests.Session:
        self.session = self.session_pool.get_session()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            # Mark if there was an error
            self.had_error = exc_type is not None
            self.session_pool.return_session(self.session, self.had_error)
            self.session = None 