#!/bin/bash

# Razer Keyboard Highlighter Setup Script for Arch Linux
# This script installs dependencies, sets up the config directory, and creates a systemd service

# Configuration
USER=$(whoami)
CONFIG_DIR="$HOME/.config/razer-keyboard-highlighter"
RAZER_CONTROLLER="razer_controller"
KEYBOARD_LISTENER="keyboard_listener"
SERVICE_NAME="keyboard_listener.service"
CONFIG_NAME="config.yaml"

# Create config directory
echo "Creating config directory: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# Copy scripts to config directory
echo "Copying script and config file to config directory..."
sudo cp "$RAZER_CONTROLLER" "/usr/bin/"
sudo cp "$KEYBOARD_LISTENER" "/usr/bin/"
chmod +x "/usr/bin/$RAZER_CONTROLLER"
chmod +x "/usr/bin/$KEYBOARD_LISTENER"

# Install Arch Linux dependencies
echo "Installing $USER required packages..."
sudo pacman -Sy --noconfirm python python-pip openrazer-daemon python-openrazer python-watchdog python-yaml
systemctl enable --now --user openrazer-daemon.service

# Add user to plugdev group
echo "Adding user to plugdev group..."
sudo gpasswd -a $USER plugdev

# Install Python dependencies
echo "Installing Root Python packages..."
sudo python -m venv /root/razer_keyboard_highlighter_venv
sudo /root/razer_keyboard_highlighter_venv/bin/pip install --upgrade pip
sudo /root/razer_keyboard_highlighter_venv/bin/pip install keyboard psutil

# Create default config file if needed
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "Creating default config.yaml..."
    cat > "$CONFIG_DIR/config.yaml" << 'EOL'
pywal: false
modes:
  base:
    rules:
      - keys: ['all']
        color: '[255,0,0]'
EOL
fi

# Create systemd service
echo "Creating systemd service..."

# Use current DISPLAY and XAUTHORITY values
CURRENT_DISPLAY=${DISPLAY:-":0"}

cat << EOL | sudo tee "/etc/systemd/system/$SERVICE_NAME" > /dev/null
[Unit]
Description=Keyboard Listener Service
After=graphical.target display-manager.service
Wants=graphical.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/keyboard_listener $USER
Environment=DISPLAY=${CURRENT_DISPLAY}

[Install]
WantedBy=default.target
EOL

# Start the service
echo "Starting service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "Installation complete!"
echo "The keyboard Listener service is now running."
echo ""
echo "Important: Log out and back in to apply group changes"
echo ""
echo "Service control:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo ""
echo "View logs: tail -f $CONFIG_DIR/logs.txt"
echo "Edit config: $CONFIG_DIR/config.yaml"
