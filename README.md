# Endesa Batch Processor

Fast batch processor for Endesa accounts with modern GUI.

## Quick Start

1. **Install:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run:**
   ```bash
   python interface.py
   ```

3. **Use:**
   - Select credentials file (format: `email:password`)
   - Set thread count (1-200)
   - Click "Start Processing"

## Features

- 🖥️ **Modern GUI** - Clean PyQt6 interface
- ⚡ **Fast Processing** - Up to 200 concurrent threads
- 📊 **Real-time Stats** - Live progress and results
- 🔄 **VPN Support** - Optional IP rotation
- 💾 **Auto Export** - Results saved to `results.txt`

## Credential Format

```
email@example.com:password
user2@example.com:pass123
```

## Files

- `interface.py` - Main GUI (run this)
- `endesa.py` - Core client
- `credentials.txt` - Your credentials
- `results.txt` - Output file

## Tips

- Start with 50 threads
- Use VPN for large batches
- Check `results.txt` for output

---
*For educational use only. Comply with Endesa's terms of service.* 