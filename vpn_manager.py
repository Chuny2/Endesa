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
        """Rotate IP by disconnecting and reconnecting with smart connect"""
        self.logger.info("Rotating IP address...")
        
        # Get current IP before rotation
        old_ip = self.get_current_ip()
        self.logger.info(f"Current IP before rotation: {old_ip}")
        
        if self.is_windows and self.evpn_api:
            try:
                # Get current location
                current_location = self.current_location
                
                # Disconnect first
                if self.is_connected:
                    self.disconnect()
                    time.sleep(1)  # Reduced from 3s to 1s
                
                # Connect to a different random location
                locations = self.evpn_api.locations
                if not locations:
                    self.logger.error("No locations available")
                    return False
                
                import random
                # Try to find a different location
                attempts = 0
                while attempts < 5:
                    location = random.choice(locations)
                    if location['name'] != current_location:
                        self.logger.info(f"Connecting to different location: {location['name']}")
                        self.evpn_api.connect(location['id'])
                        self.is_connected = True
                        self.current_location = location['name']
                        
                        # Verify connection is established
                        if self._verify_connection():
                            new_ip = self.get_current_ip()
                            if new_ip and new_ip != old_ip:
                                self.logger.info(f"IP rotation successful: {old_ip} -> {new_ip}")
                                return True
                            else:
                                self.logger.warning("IP rotation failed - same IP detected")
                                return False
                        else:
                            self.logger.warning("Connection verification failed")
                            return False
                    attempts += 1
                
                # If we couldn't find a different location, just reconnect
                self.logger.info("Couldn't find different location, reconnecting...")
                return self.connect_smart()
                
            except Exception as e:
                self.logger.error(f"Failed to rotate IP with evpn: {e}")
                return False
        else:
            # CLI approach
            # Get current location
            current_status = self.get_status()
            current_location = current_status.get('location')
            
            # Disconnect first
            if self.is_connected:
                self.disconnect()
                time.sleep(1)  # Reduced from 3s to 1s
            
            # Get available locations and try to connect to a different one
            locations = self.get_available_locations()
            if not locations:
                self.logger.error("No locations available")
                return False
            
            import random
            # Try to find a different location
            attempts = 0
            while attempts < 5:
                location = random.choice(locations)
                if location != current_location:
                    self.logger.info(f"Trying to connect to different location: {location}")
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
                            
                            # Verify connection is established
                            if self._verify_connection():
                                new_ip = self.get_current_ip()
                                if new_ip and new_ip != old_ip:
                                    self.logger.info(f"IP rotation successful: {old_ip} -> {new_ip}")
                                    return True
                                else:
                                    self.logger.warning("IP rotation failed - same IP detected")
                                    return False
                            else:
                                self.logger.warning("Connection verification failed")
                                return False
                        else:
                            self.logger.warning(f"Failed to connect to {location}: {output}")
                    else:
                        self.logger.warning(f"Failed to set region {location}: {output}")
                attempts += 1
            
            # If we couldn't find a different location, try smart connect
            self.logger.info("Couldn't find different location, trying smart connect...")
            if self.connect_smart():
                # Verify connection is established
                if self._verify_connection():
                    new_ip = self.get_current_ip()
                    if new_ip and new_ip != old_ip:
                        self.logger.info(f"IP rotation successful: {old_ip} -> {new_ip}")
                        return True
                    else:
                        self.logger.warning("IP rotation failed - same IP detected")
                        return False
                else:
                    self.logger.warning("Connection verification failed")
                    return False
            
            return False
    
    def _verify_connection(self) -> bool:
        """Verify that VPN connection is properly established"""
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                # Check VPN status
                status = self.get_status()
                if not status.get('connected', False):
                    self.logger.warning(f"VPN not connected (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(1)
                    continue
                
                # Try to get IP to verify connection is working
                ip = self.get_current_ip()
                if ip:
                    self.logger.info(f"Connection verified - IP: {ip}")
                    return True
                else:
                    self.logger.warning(f"Could not get IP (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                self.logger.warning(f"Connection verification error (attempt {attempt + 1}/{max_attempts}): {e}")
                time.sleep(1)
                continue
        
        self.logger.error("Connection verification failed after all attempts")
        return False
    
    def get_current_ip(self) -> Optional[str]:
        """Get current public IP address"""
        try:
            result = subprocess.run(
                ["curl", "-s", "https://ipinfo.io/ip"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"Failed to get IP: {e}")
        return None
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.is_windows and self.evpn_api:
            try:
                self.evpn_api.close()
            except:
                pass 