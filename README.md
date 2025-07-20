# Endesa Batch Processor

A professional tool for batch processing Endesa customer accounts to retrieve IBAN and phone information.

## Features

- **Modern PyQt6 Interface** - Clean, responsive GUI for easy configuration and monitoring
- **Batch Processing** - Process multiple credential files concurrently
- **Thread Management** - Configurable thread count (1-200 threads)
- **Real-time Progress** - Live updates and progress tracking
- **Error Handling** - Robust error handling with detailed logging
- **Results Export** - Automatic saving of results to `results.txt`

## Installation

1. **Install Dependencies:**
   ```bash
   pip3 install PyQt6 requests --break-system-packages
   ```

2. **Clone or Download the Project:**
   ```bash
   git clone <repository-url>
   cd Endesa
   ```

## Usage

### GUI Interface (Recommended)

1. **Run the Program:**
   ```bash
   python3 main.py
   ```

2. **Configure Settings:**
   - **Credentials Directory:** Select folder containing `.txt` credential files
   - **Thread Count:** Set number of concurrent threads (1-200)
   - **Start Processing:** Click "Start Processing" to begin

3. **Monitor Progress:**
   - Real-time progress updates in the output window
   - Status bar shows current processing state
   - Results automatically saved to `results.txt`

### Command Line Interface

1. **Single Account:**
   ```bash
   python3 endesa.py
   ```

2. **Batch Processing:**
   ```bash
   python3 batch_processor.py
   ```

## Credential Format

Create `.txt` files in your credentials directory with the following format:

```
email@example.com:password
```

**Example:**
```
user1@example.com:mypassword123
user2@example.com:anotherpassword
user3@example.com:thirdpassword
```

## Project Structure

```
Endesa/
├── main.py               # Main entry point - run this to start
├── interface.py          # Modern PyQt6 GUI interface
├── endesa.py            # Core Endesa client
├── config.py            # Credential management utilities
├── batch_processor.py   # Command-line batch processor
├── requirements.txt     # Python dependencies
├── credentials.txt      # Single account credentials
├── credentials/         # Directory for multiple credential files
│   ├── account1.txt
│   ├── account2.txt
│   └── ...
└── results.txt          # Output file (generated after processing)
```

## Interface Features

### Configuration Panel
- **Credentials Directory Selection:** Browse and select folder with credential files
- **Thread Count Control:** Adjustable from 1 to 200 threads
- **Auto-detection:** Automatically detects existing `credentials/` directory

### Control Panel
- **Start Processing:** Begin batch processing with current settings
- **Stop Processing:** Safely stop processing at any time
- **Real-time Status:** Live updates on processing state

### Progress Monitoring
- **Status Bar:** Current processing status and progress
- **Progress Bar:** Visual progress indicator
- **Output Window:** Real-time processing results and logs

### Results
- **Automatic Export:** Results saved to `results.txt`
- **Success/Failure Tracking:** Detailed statistics
- **Performance Metrics:** Processing time and rate information

## Performance

- **Efficient Processing:** Optimized for minimal CPU usage
- **Scalable Threading:** Supports up to 200 concurrent threads
- **Memory Efficient:** Minimal object creation and cleanup
- **Network Optimized:** Efficient session management and request handling

## Error Handling

- **Graceful Failures:** Individual account failures don't stop batch processing
- **Detailed Logging:** Comprehensive error messages and status updates
- **Recovery Options:** Ability to stop and restart processing
- **File Validation:** Automatic validation of credential files

## Security

- **Local Processing:** All processing done locally
- **No Data Storage:** Credentials not stored permanently
- **Session Management:** Proper session cleanup after processing
- **Error Isolation:** Individual account errors don't affect others

## Troubleshooting

### Common Issues

1. **Missing Dependencies:**
   ```bash
   pip3 install PyQt6 requests --break-system-packages
   ```

2. **No Credential Files Found:**
   - Ensure credential files have `.txt` extension
   - Check file format: `email:password`
   - Verify directory path is correct

3. **Authentication Errors:**
   - Verify email and password are correct
   - Check if account is active
   - Ensure no special characters in credentials

4. **Thread Count Issues:**
   - Start with lower thread counts (10-20)
   - Increase gradually based on system performance
   - Monitor system resources during processing

### Performance Tips

- **Optimal Thread Count:** Start with 50 threads, adjust based on results
- **File Organization:** Keep credential files in dedicated directory
- **System Resources:** Monitor CPU and memory usage during processing
- **Network Stability:** Ensure stable internet connection

## License

This project is for educational and personal use only. Please comply with Endesa's terms of service and applicable laws.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Verify credential format and file structure
3. Test with single account first
4. Review error messages in the output window 