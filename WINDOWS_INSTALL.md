# Windows Installation Guide

## Fix for Qt Platform Plugin Error

If you get this error:
```
qt.qpa.plugin: Could not find the Qt platform plugin "xcb"
```

## Solution 1: Install Dependencies
```bash
pip install PyQt6 PyQt6-Qt6 PyQt6-sip
```

## Solution 2: Use Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Solution 3: Manual Fix
If the above doesn't work, try:
```bash
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
pip install PyQt6==6.5.0 PyQt6-Qt6==6.5.0 PyQt6-sip==13.5.0
```

## Run the Application
```bash
python main.py
```

## Alternative: Direct Interface
```bash
python interface.py
``` 