#!/usr/bin/env python3
"""Test script to verify Windows evpn library integration"""

import sys
import platform
import logging
from vpn_manager import VPNManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_windows_vpn():
    """Test VPN functionality on Windows"""
    print(f"Testing on platform: {platform.system()}")
    print(f"Python version: {sys.version}")
    
    # Create VPN manager
    vpn = VPNManager()
    
    print(f"\nVPN Manager initialized:")
    print(f"- Is Windows: {vpn.is_windows}")
    print(f"- evpn API available: {vpn.evpn_api is not None}")
    
    if vpn.is_windows and vpn.evpn_api:
        print("\n✅ Windows evpn library detected and loaded successfully!")
        
        # Test getting available locations
        print("\nTesting available locations...")
        try:
            locations = vpn.get_available_locations()
            print(f"Found {len(locations)} available locations")
            if locations:
                print("Sample locations:")
                for loc in locations[:5]:  # Show first 5
                    print(f"  - {loc}")
        except Exception as e:
            print(f"❌ Error getting locations: {e}")
        
        # Test getting current status
        print("\nTesting status check...")
        try:
            status = vpn.get_status()
            print(f"Current status: {status}")
        except Exception as e:
            print(f"❌ Error getting status: {e}")
        
        # Test getting current IP
        print("\nTesting IP check...")
        try:
            ip = vpn.get_current_ip()
            print(f"Current IP: {ip}")
        except Exception as e:
            print(f"❌ Error getting IP: {e}")
        
        # Test connection (optional - uncomment to test)
        """
        print("\nTesting connection...")
        try:
            success = vpn.connect_smart()
            print(f"Connection result: {success}")
            if success:
                print("✅ Connection successful!")
                time.sleep(2)
                vpn.disconnect()
                print("✅ Disconnection successful!")
        except Exception as e:
            print(f"❌ Error during connection test: {e}")
        """
        
    else:
        print("\n❌ Windows evpn library not available")
        if not vpn.is_windows:
            print("This is not a Windows system")
        else:
            print("evpn library import failed")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_windows_vpn() 