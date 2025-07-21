#!/usr/bin/env python3
"""ExpressVPN integration for IP rotation using CLI commands."""

import subprocess
import time
import logging
import platform
from typing import Optional, List

class VPNManager:
    def __init__(self):
        self.logger = logging.getLogger('VPN')
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
    
    def get_status(self) -> dict:
        """Get current VPN status"""
        if self.is_windows and self.evpn_api:
            try:
                # For evpn, we need to check if it's connected
                # This is a simplified check - in practice you might want more details
                return {
                    "connected": self.is_connected,
                    "location": self.current_location,
                    "method": "evpn"
                }
            except Exception as e:
                self.logger.error(f"Error getting evpn status: {e}")
                return {"connected": False, "location": None, "error": str(e)}
        else:
            # CLI approach
            success, output = self._run_command("expressvpnctl status")
            if not success:
                return {"connected": False, "location": None, "error": output}
            
            lines = output.split('\n')
            connected = "Connected" in output
            location = None
            
            for line in lines:
                if "Connected to" in line:
                    location = line.split("Connected to")[-1].strip()
                    break
            
            return {
                "connected": connected,
                "location": location,
                "output": output,
                "method": "cli"
            }
    
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
                    "australia-sydney", "canada-toronto", "brazil", "mexico"
                ]
    
    def connect_smart_with_verification(self) -> bool:
        """Connect to VPN with intelligent IP-based verification (GENIUS USER IDEA!)
        
        This method:
        1. Gets baseline IP (real IP before VPN)
        2. Connects to VPN with retries (VPN needs time!)
        3. Verifies IP changed with retries (proof VPN is working!)
        
        Much faster and more reliable than status checking!
        """
        
        # 1. Get our baseline IP (real IP before VPN)
        self.logger.info("Getting baseline IP before VPN connection...")
        original_ip = self.get_current_ip()
        
        if not original_ip:
            self.logger.error("❌ Cannot get baseline IP - check internet connection")
            return False
        
        self.logger.info(f"📡 Baseline IP: {original_ip}")
        
        # 2. Connect to VPN using existing logic
        self.logger.info("🔗 Connecting to VPN...")
        if not self.connect_smart():  # Use existing connection method
            self.logger.error("❌ VPN connection failed")
            return False
        
        # 3. FAST RETRIES - Keep trying until IP changes from original!
        max_verification_attempts = 12  # More attempts with faster retries
        for attempt in range(max_verification_attempts):
            # Fast 0.3s delays for quick verification
            self.logger.info(f"🔍 Verifying VPN connection (attempt {attempt + 1}/{max_verification_attempts})...")
            time.sleep(0.3)  # Fast retry delay
            
            # Get new IP after VPN connection  
            new_ip = self.get_current_ip()
            
            if not new_ip:
                print(f"🔍 DEBUG: ❌ No IP detected (attempt {attempt + 1})")
                self.logger.warning(f"⚠️ Cannot get IP (attempt {attempt + 1}) - VPN still connecting...")
                continue
            
            # 4. THE GENIUS PART - Simple IP comparison!
            print(f"🔍 DEBUG: IP Comparison - Original: {original_ip} | New: {new_ip}")
            if new_ip != original_ip:
                print(f"🔍 DEBUG: ✅ IPs ARE DIFFERENT - VPN working!")
                self.logger.info(f"✅ VPN VERIFIED! IP changed: {original_ip} → {new_ip} (took {attempt + 1} attempts)")
                return True
            else:
                print(f"🔍 DEBUG: ❌ IPs ARE SAME - VPN not connected yet")
                self.logger.warning(f"⚠️ IP still unchanged: {original_ip} (attempt {attempt + 1}) - VPN still connecting...")
        
        # If we get here, all attempts failed
        self.logger.error(f"❌ VPN VERIFICATION FAILED! IP unchanged after {max_verification_attempts} attempts: {original_ip}")
        return False

    def connect_smart(self) -> bool:
        """Connect using random location selection"""
        self.logger.info("Connecting to random ExpressVPN location...")
        
        if self.is_windows and self.evpn_api:
            try:
                # For evpn, we'll connect to a random location
                locations = self.evpn_api.locations
                if not locations:
                    self.logger.error("No locations available")
                    return False
                
                import random
                location = random.choice(locations)
                self.logger.info(f"Connecting to random location: {location['name']}")
                self.evpn_api.connect(location['id'])
                self.is_connected = True
                self.current_location = location['name']
                self.logger.info("Successfully connected using evpn")
                return True
            except Exception as e:
                self.logger.error(f"Failed to connect with evpn: {e}")
                return False
        else:
            # CLI approach - connect to random location
            locations = self.get_available_locations()
            if not locations:
                self.logger.error("No locations available")
                return False
            
            import random
            location = random.choice(locations)
            self.logger.info(f"Connecting to random location: {location}")
            
            # Disconnect first if connected
            if self.is_connected:
                self.disconnect()
                time.sleep(2)
            
            # Set the region first, then connect
            success, output = self._run_command(f"expressvpnctl set region {location}")
            if success:
                self.logger.info(f"Region set to {location}")
                # Now connect to the set region
                success, output = self._run_command("expressvpnctl connect")
                if success:
                    self.logger.info(f"Successfully connected to {location}")
                    self.is_connected = True
                    self.current_location = location
                    return True
                else:
                    self.logger.error(f"Failed to connect to {location}: {output}")
            else:
                self.logger.error(f"Failed to set region {location}: {output}")
            
            # Fallback to smart connect if specific location fails
            self.logger.info("Falling back to smart connect...")
            success, output = self._run_command("expressvpnctl connect")
            if success:
                self.logger.info("Successfully connected using smart connect fallback")
                self.is_connected = True
                return True
            else:
                self.logger.error(f"Smart connect fallback failed: {output}")
                return False
    
    def connect_to_location(self, location: str) -> bool:
        """Connect to a specific location"""
        self.logger.info(f"Connecting to location: {location}")
        
        if self.is_windows and self.evpn_api:
            try:
                # Extract location ID from the string format "Name (ID: 123)"
                if "(ID:" in location:
                    location_id = int(location.split("(ID:")[1].split(")")[0].strip())
                    self.evpn_api.connect(location_id)
                    self.is_connected = True
                    self.current_location = location.split("(ID:")[0].strip()
                    self.logger.info(f"Successfully connected to {location}")
                    return True
                else:
                    self.logger.error("Invalid location format for evpn")
                    return False
            except Exception as e:
                self.logger.error(f"Failed to connect to {location}: {e}")
                return False
        else:
            # CLI approach
            # Disconnect first if connected
            if self.is_connected:
                self.disconnect()
                time.sleep(2)
            
            success, output = self._run_command(f"expressvpnctl connect {location}")
            if success:
                self.logger.info(f"Successfully connected to {location}")
                self.is_connected = True
                self.current_location = location
                return True
            else:
                self.logger.error(f"Failed to connect to {location}: {output}")
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from VPN"""
        self.logger.info("Disconnecting from VPN...")
        
        if self.is_windows and self.evpn_api:
            try:
                self.evpn_api.disconnect()
                self.logger.info("Successfully disconnected using evpn")
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
                self.logger.info("Successfully disconnected")
                self.is_connected = False
                self.current_location = None
                return True
            else:
                self.logger.error(f"Failed to disconnect: {output}")
                return False
    
    def rotate_ip(self) -> bool:
        """Rotate IP using FIXED rotation logic - prevents fake success!
        
        CRITICAL FIX: Ensures we don't think disconnection = successful rotation
        """
        self.logger.info("🔄 Rotating IP address...")
        
        # Get current IP before rotation (should be VPN IP)
        old_ip = self.get_current_ip()
        if not old_ip:
            self.logger.error("❌ Cannot get current IP for rotation")
            return False
            
        self.logger.info(f"📡 Current IP before rotation: {old_ip}")
        
        # CRITICAL: We need to remember the original real IP to detect failures!
        # For now, we'll use connect_smart_with_verification which handles this properly
        
        # Disconnect from current VPN
        if self.is_connected:
            self.logger.info("🔌 Disconnecting from current VPN...")
            self.disconnect()
            time.sleep(1)  # Brief pause
        
        # Use the GENIUS verification method for rotation!
        self.logger.info("🔗 Reconnecting with IP verification...")
        if not self.connect_smart_with_verification():
            self.logger.error("❌ VPN reconnection failed - back to real IP!")
            return False
        
        # Get final IP after successful VPN connection
        new_ip = self.get_current_ip()
        if not new_ip:
            self.logger.error("❌ Cannot get IP after VPN reconnection")
            return False
        
        # Final verification: Make sure we actually rotated
        print(f"🔄 DEBUG: FINAL Check - Old VPN: {old_ip} | New VPN: {new_ip}")
        if new_ip != old_ip:
            print(f"🔄 DEBUG: ✅ REAL ROTATION SUCCESS - Different VPN IPs!")
            self.logger.info(f"✅ IP ROTATION SUCCESS! {old_ip} → {new_ip}")
            return True
        else:
            print(f"🔄 DEBUG: ⚠️ Same VPN IP - may be same location")
            self.logger.warning(f"⚠️ IP rotation got same location: {old_ip}")
            # Still success since we have VPN, just same location
            return True
    
    def _verify_connection(self) -> bool:
        """Verify that VPN connection is properly established - SIMPLIFIED!
        
        No more complex retry loops - just check if we can get an IP.
        Real verification is done via IP comparison in connect_smart_with_verification.
        """
        try:
            # Simple check - can we get current IP?
            ip = self.get_current_ip()
            if ip:
                self.logger.info(f"Connection verified - IP: {ip}")
                return True
            else:
                self.logger.warning("Could not get IP - connection may have issues")
                return False
                
        except Exception as e:
            self.logger.warning(f"Connection verification error: {e}")
            return False
    
    def get_current_ip(self) -> Optional[str]:
        """BULLETPROOF IPv4 detection with smart retries for VPN transitions!"""
        
        # OPTIMIZED: Fast, reliable IPv4-only services in speed order
        services = [
            ("ipinfo.io", "https://ipinfo.io/ip"),         # Fast + reliable IPv4
            ("api.ipify.org", "https://api.ipify.org"),    # Fast + reliable IPv4  
            ("checkip.amazonaws.com", "https://checkip.amazonaws.com"),  # AWS reliable
            ("icanhazip.com", "http://icanhazip.com"),     # Fast but might return IPv6
        ]
        
        # SMART RETRIES: Try all services, then retry with longer timeouts if needed
        max_retry_rounds = 2  # Two rounds of attempts
        
        for retry_round in range(max_retry_rounds):
            # Progressive timeout increase for retries
            if retry_round == 0:
                # First round: Fast timeouts
                connect_timeout = "1"
                max_time = "2" 
                subprocess_timeout = 2
            else:
                # Second round: More generous timeouts for unstable VPN transitions
                connect_timeout = "2"
                max_time = "4"
                subprocess_timeout = 4
                # Brief pause between retry rounds to let VPN stabilize
                time.sleep(0.5)
        
            for service_name, service_url in services:
                try:
                    # Dynamic timeouts based on retry round
                    cmd = [
                        "curl", "-4",  # FORCE IPv4 ONLY!
                        "-s", 
                        "--connect-timeout", connect_timeout,
                        "--max-time", max_time,
                        service_url
                    ]
                
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=subprocess_timeout  # Dynamic timeout based on retry round
                    )
                
                    if result.returncode == 0 and result.stdout.strip():
                        raw_ip = result.stdout.strip()
                        
                        # STRICT IPv4 validation - NO IPv6!
                        ip_parts = raw_ip.split(".")
                        if (len(ip_parts) == 4 and 
                            all(part.isdigit() and 0 <= int(part) <= 255 for part in ip_parts)):
                            
                            return raw_ip
                        else:
                            # Skip invalid IPv4 (might be IPv6)
                            continue
                        
                except subprocess.TimeoutExpired:
                    # Service timed out, try next one
                    continue
                except Exception:
                    # Service failed, try next one
                    continue
        
        # All services failed after all retries
        self.logger.error("All IPv4 detection services failed after retries")
        return None
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.is_windows and self.evpn_api:
            try:
                self.evpn_api.close()
            except:
                pass 