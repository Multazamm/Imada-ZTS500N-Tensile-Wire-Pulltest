# Pull Tester - Quick Start Guide

## What is this?

This is a Python recreation of your wire tensile testing (Pull Tester) application. It does everything the original Pascal/Lazarus version does:

✅ Communicates with force gauge via serial port  
✅ Controls Raspberry Pi GPIO pins for automation  
✅ Stores test results in MSSQL database  
✅ Real-time force monitoring and charting  
✅ Manages multiple CNC machines  
✅ Automatic pass/fail (OK/NG) determination  

## Files Included

- **pull_tester.py** - Main application (773 lines of Python code)
- **demo.py** - Demo mode for testing without hardware
- **install.sh** - Automated installation script for Raspberry Pi
- **requirements.txt** - Python package dependencies
- **config_template.ini** - Configuration file template
- **README.md** - Complete documentation

## Quick Installation (Raspberry Pi)

```bash
# 1. Extract files to a folder
cd ~/PullTester

# 2. Run the installation script
chmod +x install.sh
./install.sh

# 3. Log out and back in (for permissions)

# 4. Edit database settings in pull_tester.py
nano pull_tester.py
# Find line ~97 and update connection_string

# 5. Run the application
python3 pull_tester.py
```

## Try the Demo (No Hardware Required)

Want to see how it works without connecting hardware?

```bash
python3 demo.py
```

This runs the application with simulated serial data. Click "START TEST" to see a simulated pull test with force curve!

## Key Improvements Over Original

1. **No Compilation** - Python runs directly, no need to compile
2. **Modern GUI** - Clean tkinter interface
3. **Better Error Handling** - Graceful failures and informative messages
4. **Cross-Platform** - Works on any system (with simulation mode)
5. **Easy Installation** - One script to install everything
6. **Development Mode** - Test without hardware using demo.py

## System Requirements

**Minimum:**
- Raspberry Pi (any model with GPIO)
- Python 3.7+
- 512MB RAM

**Recommended:**
- Raspberry Pi 3 or 4
- Python 3.9+
- 1GB+ RAM

## Hardware Connections

### Serial Port
- Connect force gauge to USB port (USB-to-Serial adapter)
- Default device: `/dev/ttyUSB0`

### GPIO Pins (BCM numbering)
- Pin 17: LED indicator
- Pin 18: Start signal (output)
- Pin 23: Stop signal (output)

## Configuration

### Database Setup

1. Install MSSQL ODBC driver (see README.md)
2. Edit connection string in `pull_tester.py`
3. Ensure database tables exist (schema in README.md)

### Serial Port

Check your device:
```bash
ls /dev/tty*
```

Update in code if needed:
```python
self.serial_device = '/dev/ttyUSB0'  # Change this
```

## Troubleshooting

### "Permission denied" on serial port
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### "Permission denied" on GPIO
```bash
sudo usermod -a -G gpio $USER
# Log out and back in
```

### Database connection fails
- Check SQL Server is running
- Verify connection string
- Test with: `isql -v your_dsn`

### Import errors
```bash
pip3 install -r requirements.txt
```

## Running at Startup

To run automatically on boot:

1. Edit crontab:
```bash
crontab -e
```

2. Add this line:
```
@reboot sleep 30 && cd /home/pi/PullTester && /usr/bin/python3 pull_tester.py
```

## Support

For detailed documentation, see **README.md**

For issues:
1. Check console output for errors
2. Verify hardware connections
3. Test in demo mode: `python3 demo.py`
4. Review README.md troubleshooting section

## Original vs Python

**Original (Pascal/Lazarus):**
- Compiled binary (61MB)
- Lazarus IDE required for changes
- Complex dependencies
- Platform-specific

**Python Version:**
- Readable source code (24KB)
- Edit with any text editor
- Simple pip install
- Runs anywhere

---

**Need Help?** Check README.md for complete documentation!
