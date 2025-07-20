#!/usr/bin/env python3
"""Comprehensive Windows compatibility test for Endesa application"""

import sys
import platform
import os
import subprocess
import importlib
from pathlib import Path

def test_platform():
    """Test platform detection"""
    print("=== Platform Test ===")
    print(f"Platform: {platform.system()}")
    print(f"Platform Release: {platform.release()}")
    print(f"Platform Version: {platform.version()}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")
    print()

def test_python_environment():
    """Test Python environment"""
    print("=== Python Environment Test ===")
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Path: {sys.path[:3]}...")  # Show first 3 paths
    print()

def test_dependencies():
    """Test required dependencies"""
    print("=== Dependencies Test ===")
    
    required_packages = [
        'PyQt6',
        'requests',
        'evpn'
    ]
    
    for package in required_packages:
        try:
            module = importlib.import_module(package)
            version = getattr(module, '__version__', 'Unknown')
            print(f"✅ {package}: {version}")
        except ImportError as e:
            print(f"❌ {package}: Not installed - {e}")
        except Exception as e:
            print(f"⚠️  {package}: Error checking version - {e}")
    print()

def test_vpn_library():
    """Test VPN library specifically"""
    print("=== VPN Library Test ===")
    
    if platform.system() == "Windows":
        try:
            from evpn import ExpressVpnApi
            print("✅ evpn library imported successfully")
            
            # Try to create API instance
            try:
                api = ExpressVpnApi()
                print("✅ ExpressVpnApi instance created")
                
                # Test basic methods
                try:
                    locations = api.locations
                    print(f"✅ Locations available: {len(locations)} locations")
                except Exception as e:
                    print(f"⚠️  Could not get locations: {e}")
                
                try:
                    api.close()
                    print("✅ API closed successfully")
                except Exception as e:
                    print(f"⚠️  Error closing API: {e}")
                    
            except Exception as e:
                print(f"❌ Could not create API instance: {e}")
                
        except ImportError as e:
            print(f"❌ evpn library not available: {e}")
    else:
        print("ℹ️  Not Windows - evpn library not needed")
    print()

def test_qt_platform():
    """Test Qt platform plugins"""
    print("=== Qt Platform Test ===")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication
        
        # Test if we can create a QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            print("✅ QApplication created successfully")
        else:
            print("✅ QApplication already exists")
            
        # Check available platforms
        print(f"Available platforms: {QCoreApplication.libraryPaths()}")
        
    except Exception as e:
        print(f"❌ Qt test failed: {e}")
    print()

def test_file_operations():
    """Test file operations"""
    print("=== File Operations Test ===")
    
    # Test current directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Test if main files exist
    main_files = ['main.py', 'interface.py', 'vpn_manager.py', 'endesa.py']
    for file in main_files:
        if Path(file).exists():
            print(f"✅ {file}: Found")
        else:
            print(f"❌ {file}: Not found")
    
    # Test credentials directory
    creds_dir = Path('credentials')
    if creds_dir.exists():
        print(f"✅ credentials directory: Found")
        cred_files = list(creds_dir.glob('*.txt'))
        print(f"  - Credential files: {len(cred_files)}")
        for file in cred_files:
            print(f"    - {file.name}")
    else:
        print(f"❌ credentials directory: Not found")
    print()

def test_network_connectivity():
    """Test network connectivity"""
    print("=== Network Connectivity Test ===")
    
    try:
        import requests
        
        # Test basic internet connectivity
        response = requests.get('https://httpbin.org/ip', timeout=10)
        if response.status_code == 200:
            ip_data = response.json()
            print(f"✅ Internet connectivity: {ip_data.get('origin', 'Unknown')}")
        else:
            print(f"❌ Internet connectivity: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Network test failed: {e}")
    print()

def test_expressvpn_cli():
    """Test ExpressVPN CLI availability"""
    print("=== ExpressVPN CLI Test ===")
    
    try:
        # Test if expressvpnctl is available
        result = subprocess.run(['expressvpnctl', 'status'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ ExpressVPN CLI available")
            print(f"Status output: {result.stdout.strip()}")
        else:
            print(f"⚠️  ExpressVPN CLI returned error: {result.stderr.strip()}")
    except FileNotFoundError:
        print("❌ ExpressVPN CLI not found in PATH")
    except Exception as e:
        print(f"❌ ExpressVPN CLI test failed: {e}")
    print()

def run_comprehensive_test():
    """Run all tests"""
    print("🔍 Comprehensive Windows Compatibility Test")
    print("=" * 50)
    
    test_platform()
    test_python_environment()
    test_dependencies()
    test_vpn_library()
    test_qt_platform()
    test_file_operations()
    test_network_connectivity()
    test_expressvpn_cli()
    
    print("=" * 50)
    print("🎯 Test Summary:")
    print("- If all tests pass, the application should work on Windows")
    print("- If evpn library fails, the app will fall back to CLI commands")
    print("- If Qt fails, check PyQt6 installation and platform plugins")
    print("- If ExpressVPN CLI fails, ensure ExpressVPN is installed")

if __name__ == "__main__":
    run_comprehensive_test() 