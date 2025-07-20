#!/usr/bin/env python3
"""Endesa client for retrieving account information."""

import json
import re
from typing import Any, Dict, Optional, Tuple

import requests


class EndesaClient:
    """Client for interacting with Endesa's customer portal."""
    
    BASE_URL = "https://www.endesaclientes.com"
    AUTH_URL = "https://accounts.enel.com/samlsso"
    
    def __init__(self, email: str, password: str, max_workers: int = 10):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.session_id = None
        
        # Optimize session for large datasets
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
            'Accept': 'text/plain, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # Scale connection pool based on thread count
        # Each thread needs connections to multiple hosts
        connections_per_host = max(10, max_workers // 2)  # At least 10, or half of max_workers
        
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,     # 5 different hosts (fixed)
            pool_maxsize=connections_per_host,  # Scale with thread count
            max_retries=1
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
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
        """Authenticate with Endesa portal."""
        session_key = self._get_session_key()
        self._authenticate(session_key)
    
    def get_account_info(self) -> Dict[str, str]:
        """Retrieve account information including IBAN and phone."""
        if not self.session_id:
            raise Exception("Not authenticated")
        
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
    
    def close(self):
        """Close the session."""
        self.session.close()


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



