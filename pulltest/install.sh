#!/bin/bash
# Pull Tester Installation Script for Raspberry Pi

echo "========================================="
echo "Pull Tester - Installation Script"
echo "========================================="
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
    echo "Detected: $MODEL"
else
    echo "Warning: Not detected as Raspberry Pi"
    echo "GPIO features may not work"
fi
echo ""

# Update system
echo "Updating system packages..."
sudo apt-get update

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y python3-pip python3-tk unixodbc unixodbc-dev

# Install Python packages
echo "Installing Python dependencies..."
pip3 install pyserial matplotlib python-dateutil

# Install RPi.GPIO if on Raspberry Pi
if command -v raspi-config &> /dev/null; then
    echo "Installing RPi.GPIO..."
    pip3 install RPi.GPIO
fi

# Install pyodbc
echo "Installing pyodbc..."
pip3 install pyodbc

# Setup permissions
echo "Setting up permissions..."
CURRENT_USER=$(whoami)

# Add user to dialout group for serial access
if ! groups $CURRENT_USER | grep -q '\bdialout\b'; then
    echo "Adding $CURRENT_USER to dialout group..."
    sudo usermod -a -G dialout $CURRENT_USER
    NEED_RELOGIN=1
fi

# Add user to gpio group for GPIO access
if command -v raspi-config &> /dev/null; then
    if ! groups $CURRENT_USER | grep -q '\bgpio\b'; then
        echo "Adding $CURRENT_USER to gpio group..."
        sudo usermod -a -G gpio $CURRENT_USER
        NEED_RELOGIN=1
    fi
fi

# Make script executable
echo "Making script executable..."
chmod +x pull_tester.py

# Create desktop shortcut
echo "Creating desktop shortcut..."
DESKTOP_FILE="$HOME/Desktop/PullTester.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Pull Tester
Comment=Wire Tensile Testing Application
Exec=/usr/bin/python3 $(pwd)/pull_tester.py
Icon=applications-science
Terminal=false
Categories=Engineering;Science;
EOF

chmod +x "$DESKTOP_FILE"

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""

if [ -n "$NEED_RELOGIN" ]; then
    echo "IMPORTANT: You need to log out and log back in"
    echo "for group permissions to take effect."
    echo ""
fi

echo "Next steps:"
echo "1. Connect your force gauge to USB port"
echo "2. Configure database connection in pull_tester.py"
echo "3. Run: python3 pull_tester.py"
echo ""
echo "Desktop shortcut created: $DESKTOP_FILE"
echo ""
echo "For more information, see README.md"
