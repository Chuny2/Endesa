# Endesa Batch Processor

Fast batch processor for Endesa accounts with modern GUI.

## Quick Start

1. **Install:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run:**
   ```bash
   python main.py
   ```

3. **Use:**
   - Select credentials file (format: `email:password`)
   - Set thread count (1-200)
   - Configure proxy (optional)
   - Click "Start Processing"

## Features

- 🖥️ **Modern GUI** - Clean PyQt6 interface
- ⚡ **Fast Processing** - Up to 200 concurrent threads
- 📊 **Real-time Stats** - Live progress and results
- 🔄 **VPN Support** - Optional IP rotation
- 🔗 **Enhanced Proxy Support** - Multiple formats with automatic parsing
- 💾 **Auto Export** - Results saved to `results.txt`

## Credential Format

```
email@example.com:password
user2@example.com:pass123
```

## Proxy Configuration

### Supported Formats

**Standard Formats:**
- `http://user:pass@host:port`
- `https://user:pass@host:port`
- `socks5://user:pass@host:port`
- `http://host:port` (no authentication)

**Alternative Formats:**
- `IP:PORT:USERNAME:PASSWORD`
- `IP:PORT:USERNAME__DOMAIN:PASSWORD`
- `USERNAME:PASSWORD@IP:PORT`

### Single Proxy
Enter one proxy in any supported format.

### Proxy Lists
Create a text file with one proxy per line (any supported format):
```
178.156.135.28:823:5f2078f075f29b78b66c__cr.ch:ef4bc9ea9b9f5fb4
http://user2:pass2@host2:port2
192.168.1.1:8080:user3:pass3
```

**Features:**
- Automatic format detection and parsing
- Proxy rotation on failures
- Connection testing and validation
- Support for mixed proxy types and formats

**Note:** Proxy is only used in normal mode. VPN mode provides its own IP rotation.

## Files

- `main.py` - Main GUI (run this)
- `src/core/endesa.py` - Core client
- `credentials.txt` - Your credentials
- `data/output/results.txt` - Output file

## Tips

- Start with 50 threads
- Use VPN for large batches
- Use proxy lists for better reliability
- Check `results.txt` for output

---
*For educational use only. Comply with Endesa's terms of service.* 