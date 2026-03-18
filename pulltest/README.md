# Pull Tester Application - Python Version

A Python-based wire tensile testing application for Raspberry Pi, recreated from the original Pascal/Lazarus version. This application interfaces with a force gauge via serial communication, controls GPIO pins for test automation, and stores results in an MSSQL database.

## Features

- **Real-time Force Monitoring**: Displays current and maximum force during pull tests
- **Multi-Machine Support**: Manage up to 14 CNC machines from a single interface
- **Serial Communication**: Interfaces with force gauge via RS232/USB serial
- **GPIO Control**: Triggers start/stop signals via Raspberry Pi GPIO pins
- **Database Integration**: Stores test results in MSSQL database
- **Live Charting**: Real-time force vs. time graph display
- **Pass/Fail Indication**: Automatic OK/NG determination based on standards
- **Test History**: View previous test results with date filtering

## Hardware Requirements

- Raspberry Pi (any model with GPIO pins)
- Force gauge with RS232/USB serial interface
- USB-to-Serial adapter (if using RS232)
- Optional: External relays/signals connected to GPIO pins

## Software Requirements

- Python 3.7 or higher
- Tkinter (usually included with Python)
- See `requirements.txt` for Python package dependencies

## Installation

### 1. Install System Dependencies

On Raspberry Pi (Debian/Ubuntu):
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-tk
sudo apt-get install unixodbc unixodbc-dev
```

### 2. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

For Raspberry Pi, also install GPIO library:
```bash
pip3 install RPi.GPIO
```

### 3. Configure Database Connection

Edit the database connection string in `pull_tester.py` (line ~97):

```python
connection_string = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=your_server_address;'
    'DATABASE=your_database_name;'
    'UID=your_username;'
    'PWD=your_password'
)
```

Install ODBC driver for SQL Server:
```bash
# On Debian/Ubuntu
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

### 4. Configure Serial Port

Update the serial device path if needed (line ~31):
```python
self.serial_device = '/dev/ttyUSB0'  # Change to your device
```

To find your serial device:
```bash
ls /dev/tty*
# or
dmesg | grep tty
```

### 5. Set Permissions

Make the script executable:
```bash
chmod +x pull_tester.py
```

Add user to dialout group for serial access:
```bash
sudo usermod -a -G dialout $USER
```

For GPIO access, add user to gpio group:
```bash
sudo usermod -a -G gpio $USER
```

Log out and back in for group changes to take effect.

## Usage

### Running the Application

```bash
python3 pull_tester.py
```

Or directly:
```bash
./pull_tester.py
```

### Operation

1. **Select Machine**: Click one of the CNC machine buttons (CNC 01 - CNC 14)
2. **Verify Information**: Check barcode, wire size, and standard values
3. **Select Terminal Side**: Choose "Side A" or "Side B" from dropdown
4. **Start Test**: Click "START TEST" button
5. **Perform Test**: The force gauge will measure the pull force
6. **View Results**: OK/NG result will be displayed and saved to database

### Running on Non-Raspberry Pi Systems

The application will run in simulation mode on systems without GPIO support:
- GPIO operations will be logged to console instead of controlling pins
- Serial communication will work normally if device is connected
- Database operations work on any system with proper ODBC setup

## Configuration

### GPIO Pin Mapping

Default GPIO pins (BCM numbering):
- Pin 17: LED indicator
- Pin 18: Start signal output
- Pin 23: Stop signal output

To change pins, edit lines 24-26 in `pull_tester.py`:
```python
self.PIN_LED = 17
self.PIN_START = 18
self.PIN_STOP = 23
```

### Serial Port Settings

Default settings (matching original application):
- Baud rate: 19200
- Data bits: 8
- Parity: None
- Stop bits: 1

### Force Gauge Commands

The application sends the following commands:
- `Y\r`: Initialize/reset
- `K\r`: Set units to Kgf
- `XAg\r`: Start continuous mode
- `Z\r`: Zero the gauge
- `XFP\r`: Force peak
- `XCW+4000+XXXX\r`: Set high/low setpoints

## Database Schema

The application expects the following table structure:

```sql
CREATE TABLE dbo.TrRPHTARIKWIRE (
    id INT IDENTITY(1,1) PRIMARY KEY,
    tanggal DATETIME,
    sift INT,
    kodemesin VARCHAR(20),
    Barcode VARCHAR(50),
    ukuranwire VARCHAR(20),
    terminala VARCHAR(50),
    terminalb VARCHAR(50),
    testarik DECIMAL(10,2),
    StatusTarik VARCHAR(10)
);

CREATE TABLE dbo.MSSTDTARIKWIRE (
    UKURAN VARCHAR(20),
    STD DECIMAL(10,2)
);
```

## Troubleshooting

### Serial Port Issues

```bash
# Check if device exists
ls -l /dev/ttyUSB0

# Check permissions
groups  # Should include 'dialout'

# Test serial port
sudo chmod 666 /dev/ttyUSB0  # Temporary fix
```

### GPIO Permission Denied

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Or run with sudo (not recommended)
sudo python3 pull_tester.py
```

### Database Connection Errors

- Verify ODBC driver is installed: `odbcinst -q -d`
- Test connection with `isql` or `tsql`
- Check firewall allows connection to SQL Server
- Verify SQL Server allows remote connections

### Import Errors

```bash
# Install missing packages
pip3 install pyserial pyodbc matplotlib

# For Raspberry Pi
pip3 install RPi.GPIO
```

## Differences from Original

This Python version maintains the same functionality as the original Pascal/Lazarus application with some improvements:

1. **Modern GUI**: Uses tkinter instead of Lazarus LCL
2. **Better Threading**: Separate thread for serial reading
3. **Improved Error Handling**: More robust exception handling
4. **Cross-Platform**: Runs on any system (with/without GPIO)
5. **Simplified Installation**: No compilation needed

## Development

### Project Structure

```
pull_tester.py       # Main application file
requirements.txt     # Python dependencies
README.md           # This file
```

### Testing Without Hardware

The application supports simulation mode:
- No serial device: Operations logged to console
- No GPIO: Pin operations logged to console
- No database: Test results logged instead of saved

### Adding Features

The code is structured in classes for easy extension:
- `PullTesterApp`: Main application class
- Methods are well-documented and separated by function
- Add custom database queries in `load_machine_data()` and `save_test_result()`

## License

This is a recreation of the original Pull Tester application. Please consult with the original software owner regarding licensing.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Verify hardware connections and permissions
3. Check console output for error messages
4. Ensure all dependencies are installed

## Version History

- v1.0 (2024): Initial Python recreation from Pascal/Lazarus original
  - Full feature parity with original application
  - Added simulation mode for development
  - Improved error handling and logging
