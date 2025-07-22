#!/usr/bin/env python3
"""Endesa client for retrieving account information."""

import json
import re
import time
import random
from typing import Any, Dict, Optional, Tuple, List

import requests
from .session_pool import SessionPool, SessionPoolManager


class EndesaClient:
    """Client for interacting with Endesa's customer portal."""
    
    BASE_URL = "https://www.endesaclientes.com"
    AUTH_URL = "https://accounts.enel.com/samlsso"
    
    def __init__(self, email: str, password: str, session_pool: SessionPool, max_retries: int = 3, retry_delay: float = 2.0, proxy: Optional[str] = None):
        self.email = email
        self.password = password
        self.session_pool = session_pool
        self.session_id = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.proxy = proxy
        
        # Parse and normalize proxy if provided
        if proxy:
            self.parsed_proxy = self._parse_proxy_format(proxy)
            if not self.parsed_proxy:
                raise ValueError(f"Could not parse proxy format: {proxy}")
            if not self._is_valid_proxy_url(self.parsed_proxy):
                raise ValueError(f"Invalid proxy URL format after parsing: {self.parsed_proxy}")
        else:
            self.parsed_proxy = None
    
    def __enter__(self):
        """Context manager entry - get session from pool."""
        self.session = self.session_pool.get_session()
        
        # Configure proxy for this session if needed
        if self.parsed_proxy:
            self.session.proxies = {
                'http': self.parsed_proxy,
                'https': self.parsed_proxy
            }
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - return session to pool."""
        if hasattr(self, 'session') and self.session:
            had_error = exc_type is not None
            self.session_pool.return_session(self.session, had_error)
            self.session = None
    
    def _parse_proxy_format(self, proxy_line: str) -> Optional[str]:
        """Parse various proxy formats and convert to standard format."""
        if not proxy_line or not isinstance(proxy_line, str):
            return None
        
        proxy_line = proxy_line.strip()
        if not proxy_line:
            return None
        
        # Format 1: Already in standard format (http://user:pass@host:port)
        if any(proxy_line.startswith(protocol) for protocol in ['http://', 'https://', 'socks5://', 'socks4://']):
            return proxy_line
        
        # Format 2: IP:PORT:USERNAME__DOMAIN:PASSWORD (your format)
        if proxy_line.count(':') == 3 and '__' in proxy_line:
            try:
                parts = proxy_line.split(':')
                if len(parts) == 4:
                    ip, port, username_domain, password = parts
                    # Extract username from username__domain
                    if '__' in username_domain:
                        username = username_domain.split('__')[0]
                        # Convert to standard format
                        return f"http://{username}:{password}@{ip}:{port}"
            except:
                pass
        
        # Format 3: IP:PORT:USERNAME:PASSWORD
        if proxy_line.count(':') == 3:
            try:
                parts = proxy_line.split(':')
                if len(parts) == 4:
                    ip, port, username, password = parts
                    return f"http://{username}:{password}@{ip}:{port}"
            except:
                pass
        
        # Format 4: IP:PORT (no authentication)
        if proxy_line.count(':') == 1:
            try:
                ip, port = proxy_line.split(':')
                return f"http://{ip}:{port}"
            except:
                pass
        
        # Format 5: USERNAME:PASSWORD@IP:PORT
        if '@' in proxy_line and proxy_line.count(':') == 2:
            try:
                auth_part, host_part = proxy_line.split('@')
                if ':' in auth_part and ':' in host_part:
                    return f"http://{proxy_line}"
            except:
                pass
        
        return None
    
    def _is_valid_proxy_url(self, proxy_url: str) -> bool:
        """Validate proxy URL format."""
        if not proxy_url or not isinstance(proxy_url, str):
            return False
        
        # Check for valid protocols
        valid_protocols = ['http://', 'https://', 'socks5://', 'socks4://']
        if not any(proxy_url.startswith(protocol) for protocol in valid_protocols):
            return False
        
        # Basic format validation
        try:
            # Remove protocol
            url_part = proxy_url.split('://', 1)[1]
            
            if '@' in url_part:  # username:password@host:port
                auth_part, host_part = url_part.split('@', 1)
                # Check if auth part has username:password format
                if ':' in auth_part:
                    username, password = auth_part.split(':', 1)
                    if not username or not password:
                        return False
                # Check if host part has host:port format
                if ':' in host_part:
                    host, port = host_part.split(':', 1)
                    if not host or not port.isdigit():
                        return False
                else:
                    return False
            else:  # host:port (no authentication)
                if ':' in url_part:
                    host, port = url_part.split(':', 1)
                    if not host or not port.isdigit():
                        return False
                else:
                    return False
            
            return True
        except Exception:
            return False
    

    
    def _find_key(self, data: Any, *keys: str) -> Optional[Any]:
        """Recursively search for keys in nested data structures."""
        if isinstance(data, dict):
            # Check direct keys first
            for key in keys:
                if key in data:
                    return data[key]
            # Recursively search values
            for value in data.values():
                result = self._find_key(value, *keys)
                if result is not None:
                    return result
        elif isinstance(data, list):
            # Search first few items to limit recursion
            for item in data[:3]:
                result = self._find_key(item, *keys)
                if result is not None:
                    return result
        return None
    
    def _get_session_key(self) -> str:
        """Retrieve session key from Endesa's authentication system."""
        # Initialize authentication
        auth_url = f"{self.BASE_URL}/sites/Satellite/?pagename=SiteEntry/NEOL/Site/Page/WrapperPage/SendParameterAuthkey&d=Touch&rand=93109&rand=73428"
        response = self.session.get(auth_url, timeout=30)
        if response.status_code in [401, 403]:
            raise Exception(f"BANNED: HTTP {response.status_code} - Account banned or blocked")
        
        # Get session key
        url = f"{self.BASE_URL}/uid-ms/saml/session-data-key"
        response = self.session.get(url, timeout=30)
        if response.status_code in [401, 403]:
            raise Exception(f"BANNED: HTTP {response.status_code} - Account banned or blocked")
        
        data = response.json()
        session_key = data.get('key')
        if not session_key:
            raise Exception("Session key not found")
        self.session_id = session_key
        return session_key
    
    def _authenticate(self, session_key: str):
        """Authenticate with Endesa using SAML."""
        auth_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': self.BASE_URL,
            'Referer': f'{self.BASE_URL}/',
            'Upgrade-Insecure-Requests': '1'
        }
        
        auth_data = {
            "tocommonauth": "true",
            "sessionDataKey": session_key,
            "username": self.email,
            "password": self.password,
            "loginButton": "Acceder ",
            "_csrftoken_": session_key,
            "o": "p"
        }
        
        response = self.session.post(self.AUTH_URL, headers=auth_headers, data=auth_data, timeout=30)
        
        if response.status_code in [401, 403]:
            raise Exception(f"BANNED: HTTP {response.status_code} - Account banned or blocked")
        
        # Extract SAML form
        form_match = re.search(r'<form[^>]*action=[\'"]([^\'"]*)[\'"][^>]*>(.*?)</form>', response.text, re.DOTALL)
        if not form_match:
            raise Exception("No SAML form found")
        
        action_url = form_match.group(1)
        form_content = form_match.group(2)
        
        # Extract form inputs
        inputs = re.findall(r'<input[^>]*name=[\'"]([^\'"]*)[\'"][^>]*value=[\'"]([^\'"]*)[\'"]', form_content)
        payload = dict(inputs)
        
        # Submit SAML response
        headers = {"User-Agent": self.session.headers["User-Agent"], "Referer": self.AUTH_URL}
        response = self.session.post(action_url, data=payload, headers=headers, timeout=30)
        
        if response.status_code in [401, 403]:
            raise Exception(f"BANNED: HTTP {response.status_code} - Account banned or blocked")
    
    def _get_user_info(self) -> Dict[str, Any]:
        """Retrieve user information from Endesa API."""
        url = f"{self.BASE_URL}/neolapi-b2c-clients-rest/authentication/userinfo"
        headers = {"Accept": "application/json", "Sessionid": self.session_id}
        response = self.session.post(url, headers=headers, json={"channel": "EWEB"}, timeout=30)
        
        if response.status_code in [401, 403]:
            raise Exception(f"BANNED: HTTP {response.status_code} - Account banned or blocked")
        
        return response.json()
    
    def _extract_account_data(self, user_data: Dict[str, Any]) -> Tuple[str, str]:
        """Extract client ID and contract number from user data."""
        clients = user_data["contactPerson"]["clients"]
        first_client = next(iter(clients.values()))
        client_id = first_client["idClient"]
        
        houses = first_client["houses"]
        first_house = next(iter(houses.values()))
        contracts = first_house["contracts"]
        first_contract = next(iter(contracts.values()))
        contract_number = first_contract["contractNumber"]
        
        return client_id, contract_number
    
    def _get_contract_info(self, client_id: str, contract_number: str) -> Dict[str, Any]:
        """Retrieve contract information from Endesa API."""
        url = f"{self.BASE_URL}/neolapi-b2c-contracts-rest/contracts/getContractInfo"
        headers = {"Accept": "application/json", "Sessionid": self.session_id}
        payload = {
            "clientId": client_id,
            "contractNumber": contract_number,
            "channel": "EWEB"
        }
        response = self.session.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in [401, 403]:
            raise Exception(f"BANNED: HTTP {response.status_code} - Account banned or blocked")
        
        return response.json()
    
    def login(self):
        """Authenticate with Endesa portal with retry mechanism for bans and connection failures."""
        for attempt in range(self.max_retries):
            try:
                session_key = self._get_session_key()
                self._authenticate(session_key)
                return  # Success, exit retry loop
            except Exception as e:
                error_msg = str(e)
                
                # Handle bans and connection errors with retries
                if "BANNED:" in error_msg or any(error_type in error_msg.lower() 
                   for error_type in ['proxy', 'connection', 'timeout', 'connect']):
                    if attempt < self.max_retries - 1:  # Not the last attempt
                        delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        time.sleep(delay)
                        continue  # Retry
                    else:
                        raise  # Last attempt failed, re-raise the exception
                else:
                    raise  # Non-retryable error, don't retry
    
    def get_account_info(self) -> Dict[str, str]:
        """Retrieve account information including IBAN and phone with retry mechanism for bans."""
        if not self.session_id:
            raise Exception("Not authenticated")
        
        for attempt in range(self.max_retries):
            try:
                user_data = self._get_user_info()
                client_id, contract_number = self._extract_account_data(user_data)
                contract_data = self._get_contract_info(client_id, contract_number)
                
                # Extract IBAN and phone
                iban = self._find_key(contract_data, "iban", "ibanaccount", "accountiban")
                phone = (
                    self._find_key(contract_data, "phone", "phonenumber") or
                    user_data.get("contactPerson", {}).get("phone")
                )
                
                return {
                    "client_id": client_id,
                    "contract_number": contract_number,
                    "iban": iban,
                    "phone": phone
                }
            except Exception as e:
                error_msg = str(e)
                if "BANNED:" in error_msg:
                    if attempt < self.max_retries - 1:  # Not the last attempt
                        delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        time.sleep(delay)
                        continue  # Retry
                    else:
                        raise  # Last attempt failed, re-raise the exception
                else:
                    raise  # Non-ban error, don't retry
    
    def close(self):
        """Close method for backward compatibility. Session management is now handled by context manager."""
        # Sessions are managed by the pool, no action needed here
        pass


def main():
    """Main function to demonstrate usage."""
    try:
        # Read credentials from file
        with open("credentials.txt", "r") as f:
            line = f.readline().strip()
            if ":" not in line:
                print("Invalid credentials file format. Use: email:password")
                return
            email, password = line.split(":", 1)
        
        # Create client and retrieve data
        client = EndesaClient(email.strip(), password.strip())
        
        client.login()
        account_info = client.get_account_info()
        
        # Display results
        print(f"IBAN: {account_info['iban']} Phone: {account_info['phone']}")
        
    except FileNotFoundError:
        print("credentials.txt not found. Create it with format: email:password")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    main()



