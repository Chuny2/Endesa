# Windows Installation Guide

This guide will help you set up the Endesa batch processor on Windows with ExpressVPN integration.

## Prerequisites

1. **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
2. **ExpressVPN** - Download and install from [expressvpn.com](https://www.expressvpn.com/)
3. **Git** (optional) - For cloning the repository

## Installation Steps

### 1. Clone or Download the Repository

```bash
git clone https://github.com/Chuny2/Endesa.git
cd Endesa
```

Or download the ZIP file and extract it.

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `PyQt6` - GUI framework
- `requests` - HTTP library
- `evpn` - ExpressVPN Python library (Windows only)

### 3. Install ExpressVPN

1. Download ExpressVPN from [expressvpn.com](https://www.expressvpn.com/)
2. Install with default settings
3. Sign in to your ExpressVPN account
4. **Important**: Make sure ExpressVPN is running in the background

### 4. Test the Installation

Run the compatibility test to verify everything is working:

```bash
python test_windows_compatibility.py
```

You should see:
- ✅ All dependencies installed
- ✅ evpn library working
- ✅ Qt platform working
- ✅ ExpressVPN CLI available

## Usage

### Basic Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Configure the interface:
   - Select number of threads
   - Choose credentials file
   - Enable/disable VPN rotation
   - Click "Start Processing"

### VPN Integration

The application supports two VPN modes:

1. **evpn Library Mode** (Windows):
   - Uses the Python evpn library
   - Faster and more reliable
   - Automatically detects available locations
   - Rotates IPs by changing locations

2. **CLI Fallback Mode**:
   - Uses ExpressVPN CLI commands
   - Works if evpn library fails
   - Same functionality but slower

### Troubleshooting

#### Qt Platform Plugin Error

If you get a Qt platform plugin error:

1. Install Visual C++ Redistributable:
   - Download from Microsoft's website
   - Install both x86 and x64 versions

2. Reinstall PyQt6:
   ```bash
   pip uninstall PyQt6
   pip install PyQt6
   ```

#### ExpressVPN Not Found

If ExpressVPN CLI is not found:

1. Make sure ExpressVPN is installed
2. Add ExpressVPN to PATH:
   - Usually: `C:\Program Files\ExpressVPN\expressvpn.exe`
   - Or restart your terminal after installation

#### evpn Library Issues

If the evpn library fails:

1. Check ExpressVPN is running
2. Try reinstalling:
   ```bash
   pip uninstall evpn
   pip install evpn
   ```
3. The app will automatically fall back to CLI mode

#### Network Issues

If you get network errors:

1. Check your internet connection
2. Make sure ExpressVPN is connected
3. Try disabling Windows Firewall temporarily
4. Check if antivirus is blocking the connection

## File Structure

```
Endesa/
├── main.py              # Main entry point
├── interface.py         # GUI interface
├── vpn_manager.py       # VPN integration
├── endesa.py           # Core Endesa client
├── requirements.txt    # Python dependencies
├── credentials/        # Credentials directory
│   └── your_file.txt   # Your credentials file
└── test_*.py          # Test scripts
```

## Security Notes

- Keep your credentials file secure
- Don't commit credentials to version control
- The `.gitignore` file excludes credential files
- Use VPN rotation to avoid rate limiting

## Support

If you encounter issues:

1. Run the compatibility test first
2. Check the troubleshooting section
3. Verify ExpressVPN is working manually
4. Check the application logs for errors

## Performance Tips

- Use 10-50 threads for optimal performance
- Enable VPN rotation for large datasets
- Keep credentials file size reasonable (< 10MB)
- Monitor system resources during processing 