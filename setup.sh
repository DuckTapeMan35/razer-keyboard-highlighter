#!/bin/bash

# Razer Keyboard Highlighter Setup Script for Arch Linux
# This script installs dependencies, sets up the config directory, and creates a systemd service

# Configuration
USER=$(whoami)
CONFIG_DIR="$HOME/.config/razer-keyboard-highlighter"
SCRIPT_NAME="razer_keyboard_highlighter.py"
SERVICE_NAME="razer-keyboard-highlighter.service"

# Verify script exists
if [ ! -f "$(pwd)/$SCRIPT_NAME" ]; then
    echo "Error: $SCRIPT_NAME not found in current directory!"
    exit 1
fi

# Create config directory
echo "Creating config directory: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# Copy script to config directory
echo "Copying script to config directory..."
cp "$(pwd)/$SCRIPT_NAME" "$CONFIG_DIR/$SCRIPT_NAME"
chmod +x "$CONFIG_DIR/$SCRIPT_NAME"

# Install Arch Linux dependencies
echo "Installing required packages..."
sudo pacman -Sy --noconfirm python python-pip python-virtualenv openrazer-daemon python-openrazer
sudo systemctl enable --now openrazer-daemon.service

# Add user to plugdev group
echo "Adding user to plugdev group..."
sudo gpasswd -a $USER plugdev

# Create Python virtual environment with system packages
echo "Creating Python virtual environment..."
virtualenv --system-site-packages "$CONFIG_DIR/.venv"

# Install Python dependencies
echo "Installing Python packages..."
"$CONFIG_DIR/.venv/bin/pip" install --upgrade pip
"$CONFIG_DIR/.venv/bin/pip" install i3ipc pynput watchdog pyyaml

# Create default config file if needed
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "Creating default config.yaml..."
    cat > "$CONFIG_DIR/config.yaml" << 'EOL'
pywal: true
key_positions: {}
modes:
  base:
    rules:
      - keys: ['all']
        color: 'color[1]'
EOL
fi

# Create systemd service
echo "Creating systemd service..."
mkdir -p "$HOME/.config/systemd/user"

# Use current DISPLAY and XAUTHORITY values
CURRENT_DISPLAY=${DISPLAY:-":0"}
CURRENT_XAUTHORITY=${XAUTHORITY:-"$HOME/.Xauthority"}

cat > "$HOME/.config/systemd/user/$SERVICE_NAME" << EOL
[Unit]
Description=Razer Keyboard Lighting Daemon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$CONFIG_DIR/.venv/bin/python $CONFIG_DIR/$SCRIPT_NAME
Restart=always
RestartSec=10
Environment="DISPLAY=$CURRENT_DISPLAY"
Environment="XAUTHORITY=$CURRENT_XAUTHORITY"
Environment="PYTHONUNBUFFERED=1"
Environment="HOME=$HOME"
Environment="USER=$USER"
StandardOutput=file:$CONFIG_DIR/service.log
StandardError=file:$CONFIG_DIR/service.log

[Install]
WantedBy=default.target
EOL

# Enable user services
echo "Enabling user service persistence..."
sudo loginctl enable-linger $USER

# Start the service
echo "Starting service..."
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

echo "Installation complete!"
echo "The keyboard lighting service is now running."
echo ""
echo "Important: Log out and back in to apply group changes"
echo ""
echo "Service control:"
echo "  systemctl --user status $SERVICE_NAME"
echo "  systemctl --user restart $SERVICE_NAME"
echo ""
echo "View logs: tail -f $CONFIG_DIR/service.log"
echo "Edit config: $CONFIG_DIR/config.yaml"
