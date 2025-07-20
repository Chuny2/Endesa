#!/usr/bin/env python3
"""Credential management utilities."""

from typing import Optional, Tuple


def read_credentials(filepath: str) -> Optional[Tuple[str, str]]:
    """Read credentials from a text file in email:password format."""
    try:
        with open(filepath, 'r') as f:
            line = f.readline().strip()
            if ':' in line:
                email, password = line.split(':', 1)
                return email.strip(), password.strip()
    except:
        pass
    return None


def is_valid_credentials(email: str, password: str) -> bool:
    """Validate that credentials are not empty."""
    return bool(email and password) 