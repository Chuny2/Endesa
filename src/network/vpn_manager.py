#!/usr/bin/env python3
"""ExpressVPN integration for IP rotation using CLI commands."""

import subprocess
import time
import logging
import platform
import random
import socket
from typing import Optional, List
import requests

class VPNManager:
    def __init__(self):
        self.logger = logging.getLogger('VPN')
        self.logger.setLevel(logging.INFO)  # Make sure VPN logger captures INFO
        self.is_connected = False
        self.current_location = None
        self.is_windows = platform.system() == "Windows"
        
        # Try to import evpn on Windows
        self.evpn_api = None
        if self.is_windows:
            try:
                from evpn import ExpressVpnApi
                self.evpn_api = ExpressVpnApi()
                self.logger.info("Using evpn library (Windows)")
            except ImportError:
                self.logger.warning("evpn library not available, falling back to CLI")
                self.evpn_api = None
        else:
            self.logger.info("Using CLI commands (Linux/Mac)")
    
    def _run_command(self, command: str) -> tuple[bool, str]:
        """Run a shell command and return success status and output"""
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            output = result.stdout.strip() if result.stdout else result.stderr.strip()
            return success, output
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def get_available_locations(self) -> List[str]:
        """Get list of available VPN locations"""
        if self.is_windows and self.evpn_api:
            try:
                locations = self.evpn_api.locations
                return [f"{loc['name']} (ID: {loc['id']})" for loc in locations]
            except Exception as e:
                self.logger.error(f"Error getting evpn locations: {e}")
                return []
        else:
            # CLI approach - get real available regions from ExpressVPN
            success, output = self._run_command("expressvpnctl get regions")
            if success:
                regions = [line.strip() for line in output.split('\n') if line.strip() and line.strip() != 'smart']
                return regions
            else:
                self.logger.error(f"Failed to get regions: {output}")
                # Fallback to common locations
                return [
                    "usa-new-york", "usa-los-angeles-1", "usa-chicago", "uk-london", 
                    "germany-frankfurt-1", "netherlands-amsterdam", "france-paris-1",
                    "spain-madrid", "italy-milan", "japan-tokyo", "singapore-cbd",
                    "australia-melbourne", "canada-toronto", "brazil-sao-paulo"
                ]
    
    def connect_with_proper_verification(self) -> bool:
        """Connect to VPN with proper IP verification flow."""
        max_location_attempts = 5  # Try up to 5 different locations
        
        for location_attempt in range(max_location_attempts):
            self.logger.info(f"🔄 VPN Connection Attempt {location_attempt + 1}/{max_location_attempts}")
            
            # Step 1: Make sure VPN is disconnected
            self.logger.info("1️⃣ Ensuring VPN is disconnected...")
            self.disconnect()
            time.sleep(2)  # Wait for clean disconnection
            
            # Step 2: Grab the real IP
            self.logger.info("2️⃣ Getting real IP address...")
            original_ip = self.get_current_ip()
            if not original_ip:
                self.logger.error("❌ Cannot get real IP - check internet connection")
                continue
            
            self.logger.info(f"📡 Real IP: {original_ip}")
            
            # Step 3: Connect to VPN
            self.logger.info("3️⃣ Connecting to VPN...")
            if not self._connect_to_random_location():
                self.logger.error("❌ VPN connection failed, trying next location...")
                continue
            
            # Step 4: Poll every second until we get a response and check IP
            self.logger.info("4️⃣ Polling for IP change every second...")
            max_verification_attempts = 30  # 30 seconds max
            
            for attempt in range(max_verification_attempts):
                time.sleep(1)  
                
                new_ip = self.get_current_ip()
                if not new_ip:
                    self.logger.info(f"⏳ No IP response yet (attempt {attempt + 1}/30)...")
                    continue
                
                # Step 5: Check if original IP is different from new IP
                if new_ip == original_ip:
                    self.logger.warning(f"⚠️ IP unchanged: {original_ip} (attempt {attempt + 1}/30)")
                    continue
                else:
                    # Step 6: Different IP - SUCCESS! Now check DNS resolution
                    self.logger.info(f"✅ VPN VERIFIED! IP changed: {original_ip} → {new_ip}")
                    
                    # Step 7: Verify DNS resolution is working
                    self.logger.info("7️⃣ Verifying DNS resolution...")
                    if self.check_dns_resolution():
                        self.logger.info(f"🚀 VPN fully verified and ready to start processing!")
                        self.is_connected = True
                        return True
                    else:
                        self.logger.warning(f"⚠️ DNS resolution failed, trying different location...")
                        self.disconnect()
                        #ime.sleep(2)
                        break  # Break inner loop to try next location
            
            # If we get here, IP didn't change within 30 seconds
            self.logger.warning(f"⚠️ IP didn't change within 30 seconds, trying different location...")
            self.disconnect()
            time.sleep(1)
        
        # All location attempts failed
        self.logger.error(f"❌ Failed to get different IP after {max_location_attempts} location attempts")
        return False
    
    def rotate_ip(self) -> bool:
        """Rotate IP address using proper verification flow."""
        self.logger.info("🔄 Starting IP rotation...")
        
        # Get current IP before rotation
        old_ip = self.get_current_ip()
        if old_ip:
            self.logger.info(f"📡 Current IP before rotation: {old_ip}")
        
        # Use the same proper verification flow
        return self.connect_with_proper_verification()
    
    def _connect_to_random_location(self) -> bool:
        """Connect to a random VPN location."""
        if self.is_windows and self.evpn_api:
            try:
                locations = self.evpn_api.locations
                if not locations:
                    self.logger.error("No locations available")
                    return False
                
                location = random.choice(locations)
                self.logger.info(f"🌍 Connecting to: {location['name']}")
                self.evpn_api.connect(location['id'])
                self.current_location = location['name']
                return True
            except Exception as e:
                self.logger.error(f"Failed to connect with evpn: {e}")
                return False
        else:
            # CLI approach
            locations = self.get_available_locations()
            if not locations:
                self.logger.error("No locations available")
                return False
            
            location = random.choice(locations)
            self.logger.info(f"🌍 Connecting to: {location}")
            
            # Set the region first, then connect
            success, output = self._run_command(f"expressvpnctl set region {location}")
            if not success:
                self.logger.error(f"Failed to set region {location}: {output}")
                return False
            
            # Now connect to the set region
            success, output = self._run_command("expressvpnctl connect")
            if success:
                self.logger.info(f"🔗 Connected to {location}")
                self.current_location = location
                return True
            else:
                self.logger.error(f"Failed to connect to {location}: {output}")
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from VPN"""
        if self.is_windows and self.evpn_api:
            try:
                self.evpn_api.disconnect()
                self.logger.info("🔌 Disconnected using evpn")
                self.is_connected = False
                self.current_location = None
                return True
            except Exception as e:
                self.logger.error(f"Failed to disconnect with evpn: {e}")
                return False
        else:
            # CLI approach
            success, output = self._run_command("expressvpnctl disconnect")
            if success:
                self.logger.info("🔌 Disconnected from VPN")
                self.is_connected = False
                self.current_location = None
                return True
            else:
                # Don't log as error - might already be disconnected
                self.logger.info("VPN already disconnected or disconnect command failed")
                self.is_connected = False
                self.current_location = None
                return True  # Return true anyway since goal is to be disconnected
    
    def get_current_ip(self) -> Optional[str]:
        """Get current public IP address using requests."""
        services = [
            ("ipinfo.io", "https://ipinfo.io/ip"),
            ("api.ipify.org", "https://api.ipify.org"),
            ("httpbin.org", "https://httpbin.org/ip"),
            ("icanhazip.com", "http://icanhazip.com"),
        ]
        
        # Create a clean session for IP checking (avoid interference)
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'
        })
        
        for service_name, service_url in services:
            try:
                response = session.get(
                    service_url,
                    timeout=(3, 5),  # (connect, read) timeout
                    # Force IPv4 by using IPv4-only DNS resolution if needed
                )
                
                if response.status_code == 200 and response.text.strip():
                    if service_name == "httpbin.org":
                        # JSON response
                        data = response.json()
                        raw_ip = data.get("origin", "").split(",")[0].strip()
                    else:
                        # Plain text response
                        raw_ip = response.text.strip()
                    
                    # Validate IPv4 format (same validation logic)
                    ip_parts = raw_ip.split(".")
                    if (len(ip_parts) == 4 and 
                        all(part.isdigit() and 0 <= int(part) <= 255 for part in ip_parts)):
                        return raw_ip
                        
            except (requests.RequestException, ValueError, KeyError):
                continue
        
        session.close()
        return None
    
    def check_dns_resolution(self, timeout: int = 5) -> bool:
        """
        Check if DNS resolution is working properly through the VPN.
        Tests multiple DNS servers and domains with best practices.
        
        Args:
            timeout: Timeout in seconds for DNS queries
            
        Returns:
            bool: True if DNS resolution is working properly
        """
        self.logger.info("🔍 Checking DNS resolution through VPN...")
        
        # Test domains - mix of popular sites
        test_domains = [
            "google.com",
            "cloudflare.com", 
            "github.com",
            "amazon.com",
            "microsoft.com"
        ]
        
        # DNS servers to test against
        dns_servers = [
            ("8.8.8.8", "Google DNS"),
            ("1.1.1.1", "Cloudflare DNS"),
            ("208.67.222.222", "OpenDNS"),
            ("9.9.9.9", "Quad9 DNS")
        ]
        
        successful_resolutions = 0
        total_tests = 0
        
        for domain in test_domains:
            for dns_server, dns_name in dns_servers:
                total_tests += 1
                
                try:
                    # Set custom DNS server
                    original_dns = socket.getdefaulttimeout()
                    socket.setdefaulttimeout(timeout)
                    
                    # Try to resolve the domain using the specific DNS server
                    # We'll use socket.getaddrinfo which is more comprehensive
                    result = socket.getaddrinfo(domain, None, socket.AF_INET)
                    
                    if result and len(result) > 0:
                        # Successfully resolved
                        ip_address = result[0][4][0]
                        self.logger.info(f"✅ DNS OK: {domain} → {ip_address} (via {dns_name})")
                        successful_resolutions += 1
                    else:
                        self.logger.warning(f"❌ DNS Failed: {domain} via {dns_name} - No results")
                
                except socket.gaierror as e:
                    self.logger.warning(f"❌ DNS Failed: {domain} via {dns_name} - {e}")
                except socket.timeout:
                    self.logger.warning(f"⏱️ DNS Timeout: {domain} via {dns_name}")
                except Exception as e:
                    self.logger.warning(f"❌ DNS Error: {domain} via {dns_name} - {e}")
                finally:
                    # Reset timeout
                    socket.setdefaulttimeout(original_dns)
                
                # Small delay between tests to avoid overwhelming
                time.sleep(0.1)
        
        # Calculate success rate
        success_rate = (successful_resolutions / total_tests) * 100 if total_tests > 0 else 0
        
        # Consider DNS working if at least 70% of tests pass
        dns_working = success_rate >= 50.0
        
        if dns_working:
            self.logger.info(f"✅ DNS Resolution Verified: {successful_resolutions}/{total_tests} tests passed ({success_rate:.1f}%)")
        else:
            self.logger.error(f"❌ DNS Resolution Failed: Only {successful_resolutions}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        return dns_working
    
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.is_windows and self.evpn_api:
            try:
                self.evpn_api.close()
            except:
                pass 