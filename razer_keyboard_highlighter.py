#!/usr/bin/env python3
from openrazer.client import DeviceManager
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import threading
import time
import yaml
import os
import re
import traceback
from collections import deque
from typing import Dict, List, Tuple, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Conditionally import i3ipc only if needed
try:
    import i3ipc
    I3_AVAILABLE = True
except ImportError:
    I3_AVAILABLE = False

class PywalFileHandler(FileSystemEventHandler):
    """Handles pywal color file changes"""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def on_modified(self, event):
        if event.src_path.endswith('colors'):
            self.callback()

class ConfigFileHandler(FileSystemEventHandler):
    """Handles config file changes"""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def on_modified(self, event):
        if event.src_path.endswith('config.yaml'):
            self.callback()

class KeyboardController:
    def __init__(self):
        try:
            # Initialize with error handling
            print("Initializing keyboard controller...")
            
            # Load configuration first
            self.config = self.load_config()
            
            # Initialize device manager and find keyboard
            self.device_manager = DeviceManager()
            print("Device manager created")
            self.razer_keyboard = self.find_keyboard()
            
            if not self.razer_keyboard:
                raise RuntimeError("Razer keyboard not found")
            
            # Get keyboard dimensions as integers
            self.rows = int(self.razer_keyboard.fx.advanced.rows)
            self.cols = int(self.razer_keyboard.fx.advanced.cols)
            print(f"Keyboard dimensions: {self.rows} rows x {self.cols} cols")
            
            # Parse key positions
            self.key_positions = self.parse_key_positions()
            print(f"Loaded key positions for: {', '.join(self.key_positions.keys())}")
            
            # Initialize other components
            self.active_modifiers = set()
            self.non_empty_workspaces = []
            self.pressed_keys = deque()  # Track keys in press order
            self.colors_lock = threading.Lock()
            self.colors = self.load_colors()
            self.key_listener = None
            self.i3_thread = None
            self.pywal_updated = False
            self.config_updated = False
            self.pywal_watchdog_observer = None
            self.config_watchdog_observer = None
            self.current_mode = "base"
            
            # Define modifier keys
            self.modifier_keys = {
                Key.cmd: 'super',
                Key.shift: 'shift',
                Key.shift_r: 'shift',
                Key.alt: 'alt',
                Key.alt_r: 'alt',
                Key.ctrl: 'ctrl',
                Key.ctrl_r: 'ctrl'
            }
            
            # Check if i3 integration is needed
            self.i3_enabled = self.config.get('i3', False) or self.needs_i3_integration()
            print(f"i3 integration: {'ENABLED' if self.i3_enabled else 'DISABLED'}")
            
            # Create lock only if i3 is enabled
            if self.i3_enabled:
                self.i3_lock = threading.Lock()
            else:
                self.i3_lock = None
            
            # Ensure base mode is defined
            if 'modes' not in self.config:
                self.config['modes'] = {}
            if 'base' not in self.config['modes']:
                self.config['modes']['base'] = {'rules': [{'keys': ['all'], 'color': 'color[1]'}]}
            
            print("Keyboard controller initialized successfully")
            
        except Exception as e:
            print(f"Initialization failed: {e}")
            traceback.print_exc()
            raise

    def needs_i3_integration(self) -> bool:
        """Check if any rules require i3 workspace information"""
        if not I3_AVAILABLE:
            return False
            
        for mode_name, mode_config in self.config.get('modes', {}).items():
            for rule in mode_config.get('rules', []):
                if rule.get('condition') == 'non_empty_workspaces':
                    return True
        return False

    def load_config(self) -> Dict[str, Any]:
        """Load YAML configuration from script directory"""
        try:
            # Get config file
            script_dir = os.path.expanduser('~/.config/razer-keyboard-highlighter')
            config_path = os.path.join(script_dir, 'config.yaml')
            print(f"Loading config from: {config_path}")
            
            if not os.path.exists(config_path):
                print("Config file not found, using default configuration")
                return {
                    'pywal': True,
                    'i3': False,  # Disable i3 by default
                    'key_positions': {},
                    'log': True,
                    'modes': {
                        'base': {
                            'rules': [
                                {'keys': ['all'], 'color': 'color[1]'}
                            ]
                        }
                    }
                }
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if 'log' not in config:
                    config['log'] = False
                print("Config loaded successfully")
                return config
                
        except Exception as e:
            print(f"Error loading config: {e}")
            traceback.print_exc()
            return {}

    def should_log(self) -> bool:
        """Check if logging is enabled in config"""
        return self.config.get('log', True)

    def parse_key_positions(self) -> Dict[str, List[Tuple[int, int]]]:
        """Parse key positions from config, with fallback values"""
        positions = {}
        
        # Create 'all' key group using actual keyboard dimensions
        positions['all'] = [(r, c) for r in range(self.rows) for c in range(self.cols)]
        
        # Load positions from config
        if 'key_positions' in self.config:
            for key, value in self.config['key_positions'].items():
                try:
                    if isinstance(value, list):
                        # Convert all elements to (int, int)
                        converted = []
                        for item in value:
                            if isinstance(item, (list, tuple)) and len(item) == 2:
                                converted.append((int(item[0]), int(item[1])))
                            elif isinstance(item, str) and item.startswith('(') and item.endswith(')'):
                                # Safely parse string tuple
                                try:
                                    # Remove parentheses and split
                                    stripped = item.strip()[1:-1]
                                    parts = stripped.split(',')
                                    if len(parts) == 2:
                                        row = int(parts[0].strip())
                                        col = int(parts[1].strip())
                                        converted.append((row, col))
                                    else:
                                        if self.should_log():
                                            print(f"Invalid tuple format for key '{key}': {item}")
                                except ValueError as e:
                                    if self.should_log():
                                        print(f"Error parsing position '{item}' for key '{key}': {e}")
                            else:
                                if self.should_log():
                                    print(f"Invalid position format for key '{key}': {item}")
                        positions[key] = converted
                    elif isinstance(value, (tuple, list)) and len(value) == 2:
                        # Single position
                        positions[key] = [(int(value[0]), int(value[1]))]
                    else:
                        if self.should_log():
                            print(f"Invalid position format for key '{key}': {value}")
                        positions[key] = []
                except Exception as e:
                    if self.should_log():
                        print(f"Error parsing position for key '{key}': {e}")
                    positions[key] = []
        
        # Add default positions for essential keys as integers
        defaults = {
            'super': [(5, 1)],
            'enter': [(3, 13)],
            'numbers': [(1,1), (1,2), (1,3), (1,4), (1,5), (1,6), (1,7), (1,8), (1,9), (1,10)],
            'arrows': [(5,14), (5,15), (5,16), (4,15)],
            'shift': [(4,0)],
            'alt': [(5,2)],
            'ctrl': [(5,0)],
            'q': [(2,1)],
            'd': [(3,3)],
            'x': [(4,3)],
            'z': [(4,2)],
            'space': [(5,7)],
            'tab': [(2,0)],
            'esc': [(1,0)],
            'backspace': [(1,15)],
        }
        
        for key, pos_list in defaults.items():
            if key not in positions:
                # Convert to list of integer tuples
                positions[key] = [(int(r), int(c)) for r, c in pos_list]
                if self.should_log():
                    print(f"Added default position for key '{key}'")
        
        # Ensure all positions are integers
        for key in positions:
            new_list = []
            for pos in positions[key]:
                if isinstance(pos, (tuple, list)) and len(pos) == 2:
                    new_list.append((int(pos[0]), int(pos[1])))
            positions[key] = new_list
        
        return positions

    def find_keyboard(self):
        """Find Razer keyboard device by VID/PID"""
        print("Searching for Razer keyboards by VID/PID...")
        
        # List of known Razer keyboard VID/PID combinations
        razer_keyboards = {
            "1532:010D", "1532:010E", "1532:010F", "1532:0118", "1532:011A",
            "1532:011B", "1532:011C", "1532:0202", "1532:0203", "1532:0204",
            "1532:0205", "1532:0209", "1532:020F", "1532:0210", "1532:0211",
            "1532:0214", "1532:0216", "1532:0217", "1532:021A", "1532:021E",
            "1532:021F", "1532:0220", "1532:0221", "1532:0224", "1532:0225",
            "1532:0226", "1532:0227", "1532:0228", "1532:022A", "1532:022C",
            "1532:022D", "1532:022F", "1532:0232", "1532:0233", "1532:0234",
            "1532:0235", "1532:0237", "1532:0239", "1532:023A", "1532:023B",
            "1532:023F", "1532:0240", "1532:0241", "1532:0243", "1532:0245",
            "1532:0246", "1532:024A", "1532:024B", "1532:024C", "1532:024D",
            "1532:024E", "1532:0252", "1532:0253", "1532:0255", "1532:0256",
            "1532:0257", "1532:0258", "1532:0259", "1532:025A", "1532:025C",
            "1532:025D", "1532:025E", "1532:0266", "1532:0268", "1532:0269",
            "1532:026A", "1532:026B", "1532:026C", "1532:026D", "1532:026E",
            "1532:026F", "1532:0270", "1532:0271", "1532:0276", "1532:0279",
            "1532:027A", "1532:0282", "1532:0287", "1532:028A", "1532:028B",
            "1532:028C", "1532:028D", "1532:028F", "1532:0290", "1532:0292",
            "1532:0293", "1532:0294", "1532:0295", "1532:0296", "1532:0298",
            "1532:029D", "1532:029E", "1532:029F", "1532:02A0", "1532:02A1",
            "1532:02A2", "1532:02A3", "1532:02A5", "1532:02A6", "1532:02B6",
            "1532:02B8", "1532:0A24"
        }
        
        for device in self.device_manager.devices:
            # Format VID/PID as "vid:pid" string
            vidpid = f"{device._vid:04X}:{device._pid:04X}"
            if self.should_log():
                print(f"Checking device: {device.name} (VID:PID={vidpid})")
            
            if vidpid in razer_keyboards:
                if self.should_log():
                    print(f"Using keyboard: {device.name} (VID:PID={vidpid})")
                return device
        if self.should_log():
            print("No Razer keyboard found with known VID/PID")
        return None

    def load_colors(self) -> List[Tuple[int, int, int]]:
        """Load colors from pywal or use defaults"""
        if self.config.get('pywal', True):
            colors = self.read_wal_colors('/home/duck/.cache/wal/colors')
            if colors:
                if self.should_log():
                    print(f"Loaded {len(colors)} colors from pywal")
                return colors
            else:
                if self.should_log():
                    print("Using fallback colors")
                return [
                    (55, 59, 67),    # Background
                    (171, 178, 191),  # Foreground
                    (191, 97, 106),   # Red
                    (163, 190, 140),  # Green
                    (224, 175, 104),  # Yellow
                    (129, 162, 190),  # Blue
                    (180, 142, 173),  # Magenta
                    (139, 213, 202),  # Cyan
                    (92, 99, 112)     # Light gray
                ]
        else:
            if self.should_log():
                print("Pywal disabled, using default colors")
            return [
                (100, 100, 100),  # Default color
                (200, 200, 200)   # Highlight color
            ]

    def read_wal_colors(self, file_path: str) -> List[Tuple[int, int, int]]:
        """Read colors from pywal cache file"""
        try:
            rgb_colors = []
            if not os.path.exists(file_path):
                if self.should_log():
                    print(f"Wal colors file not found at {file_path}")
                return []
                
            with open(file_path, 'r') as file:
                for line in file:
                    cleaned = line.strip()
                    if not cleaned:
                        continue
                    hex_color = cleaned.lstrip('#').strip()
                    if len(hex_color) == 6:
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        rgb_colors.append((r, g, b))
            return rgb_colors
        except Exception as e:
            if self.should_log():
                print(f"Error reading wal colors: {e}")
            return []

    def resolve_color(self, color_spec: Any) -> Tuple[int, int, int]:
        """Convert color specification to RGB tuple"""
        try:
            # Handle RGB list
            if isinstance(color_spec, list) and len(color_spec) == 3:
                return tuple(color_spec)
            
            # Handle string specifications
            if isinstance(color_spec, str):
                # Handle color[n] specification
                match = re.match(r'color\[(\d+)\]', color_spec)
                if match:
                    idx = int(match.group(1))
                    if idx < len(self.colors):
                        return self.colors[idx]
                
                # Handle hex colors
                elif color_spec.startswith('#'):
                    hex_color = color_spec[1:]
                    if len(hex_color) == 6:
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        return (r, g, b)
        except Exception as e:
            if self.should_log():
                print(f"Error resolving color {color_spec}: {e}")
        
        return (0, 0, 0)  # Default to black

    def find_non_empty_workspaces(self):
        """Get list of non-empty workspaces from i3 (if enabled)"""
        if not self.i3_enabled or not I3_AVAILABLE:
            return []
            
        try:
            i3 = i3ipc.Connection()
            workspaces = i3.get_workspaces()
            tree = i3.get_tree()
            workspace_names = []
            
            for ws in workspaces:
                if ws.name == "__i3_scratch":
                    continue
                for container in tree.workspaces():
                    if container.name == ws.name:
                        if container.leaves():
                            workspace_names.append(ws.name)
                        break
            return workspace_names
        except Exception as e:
            if self.should_log():
                print(f"Error getting workspaces: {e}")
            return []

    def update_workspaces(self):
        """Update workspace status (only if i3 enabled)"""
        if not self.i3_enabled:
            return
            
        if self.i3_lock:
            with self.i3_lock:
                try:
                    self.non_empty_workspaces = self.find_non_empty_workspaces()
                    if self.should_log():
                        print(f"Updated workspaces: {self.non_empty_workspaces}")
                except Exception as e:
                    if self.should_log():
                        print(f"Error updating workspaces: {e}")
        else:
            try:
                self.non_empty_workspaces = self.find_non_empty_workspaces()
                if self.should_log():
                    print(f"Updated workspaces: {self.non_empty_workspaces}")
            except Exception as e:
                if self.should_log():
                    print(f"Error updating workspaces: {e}")

    def reload_config(self):
        """Reload configuration from file"""
        with self.colors_lock:
            try:
                self.config = self.load_config()
                self.key_positions = self.parse_key_positions()
                self.colors = self.load_colors()
                
                # Re-evaluate i3 requirement
                self.i3_enabled = self.config.get('i3', False) or self.needs_i3_integration()
                if self.should_log():
                    print(f"i3 integration: {'ENABLED' if self.i3_enabled else 'DISABLED'}")
                    print("Configuration reloaded")

                self.config_updated = False
                # Update lighting after reload
                self.update_lighting()
            except Exception as e:
                if self.should_log():
                    print(f"Error reloading config: {e}")

    def get_keys_positions(self, key_spec: Any) -> List[Tuple[int, int]]:
        """Get positions for a key or key group"""
        try:
            if isinstance(key_spec, str):
                return self.key_positions.get(key_spec, [])
            elif isinstance(key_spec, list):
                positions = []
                for k in key_spec:
                    positions.extend(self.get_keys_positions(k))
                return positions
        except Exception as e:
            if self.should_log():
                print(f"Error getting positions for {key_spec}: {e}")
        return []

    def apply_rule(self, rule: Dict[str, Any]):
        """Apply a lighting rule from configuration"""
        try:
            # Get key positions
            keys = rule.get('keys', [])
            positions = self.get_keys_positions(keys)
            if not positions:
                if self.should_log():
                    print(f"No positions found for keys: {keys}")
                return
            
            # Handle per-key colors
            if 'colors' in rule:
                if self.should_log():
                    print(f"Applying per-key colors for {keys}")
                colors = [self.resolve_color(c) for c in rule['colors']]
                for i, pos in enumerate(positions):
                    try:
                        row = int(pos[0])
                        col = int(pos[1])
                        if i < len(colors):
                            self.razer_keyboard.fx.advanced.matrix[row, col] = colors[i]
                    except (ValueError, TypeError):
                        continue
            
            # Handle conditional rules
            condition = rule.get('condition')
            if condition == 'non_empty_workspaces':
                # Skip if i3 not enabled
                if not self.i3_enabled:
                    if self.should_log():
                        print("Skipping workspace condition - i3 disabled")
                    return
                    
                value = rule.get('value')
                color = self.resolve_color(rule.get('color'))
                if self.should_log():
                    print(f"Applying condition for {keys}: non_empty={value}")
                
                # Only apply to number keys
                if keys == ['numbers']:
                    for i, pos in enumerate(positions):
                        try:
                            row = int(pos[0])
                            col = int(pos[1])
                            workspace_num = str(i + 1)
                            if (workspace_num in self.non_empty_workspaces) == value:
                                self.razer_keyboard.fx.advanced.matrix[row, col] = color
                        except (ValueError, TypeError):
                            continue
                return
            
            # Handle simple color rule
            if 'color' in rule:
                color = self.resolve_color(rule['color'])
                if self.should_log():
                    print(f"Setting {keys} to {color}")
                for pos in positions:
                    try:
                        row = int(pos[0])
                        col = int(pos[1])
                        self.razer_keyboard.fx.advanced.matrix[row, col] = color
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            if self.should_log():
                print(f"Error applying rule: {e}")
            traceback.print_exc()

    def normalize_key_event(self, key) -> str:
        """Convert any key press event to consistent string representation"""
        # Handle special keys
        if key == Key.enter:
            return 'enter'
        if key == Key.space:
            return 'space'
        if key == Key.tab:
            return 'tab'
        if key == Key.esc:
            return 'esc'
        if key == Key.backspace:
            return 'backspace'
        if key == Key.cmd:
            return 'super'
        if key in (Key.shift, Key.shift_r):
            return 'shift'
        if key in (Key.alt, Key.alt_r):
            return 'alt'
        if key in (Key.ctrl, Key.ctrl_r):
            return 'ctrl'
        
        # Handle character keys
        if isinstance(key, KeyCode) and key.char:
            return key.char.lower()
        
        # Fallback to key name
        return key.name.lower() if hasattr(key, 'name') else str(key)

    def get_current_mode(self) -> str:
        """Determine current mode based on active modifiers with consistent ordering"""
        try:
            # Get active modifier names in sorted order for consistent mode names
            active_mod_names = sorted({
                self.modifier_keys[k] 
                for k in self.active_modifiers 
                if k in self.modifier_keys
            })
            
            # Create mode name from active modifiers
            if active_mod_names:
                mode_name = '_'.join(active_mod_names)
                if mode_name in self.config.get('modes', {}):
                    self.current_mode = mode_name
                    if self.should_log():
                        print(f"Active modifier mode: {mode_name}")
                    return mode_name
            
            # Check for full key sequence mode only if no modifiers are active
            if self.pressed_keys:
                full_sequence = '_'.join(self.pressed_keys)
                if full_sequence in self.config.get('modes', {}):
                    self.current_mode = full_sequence
                    if self.should_log():
                        print(f"Key sequence mode: {full_sequence}")
                    return full_sequence
            
            # Fallback to base mode if no special mode is active
            return 'base'
        except Exception as e:
            if self.should_log():
                print(f"Error determining current mode: {e}")
            return 'base'

    def update_lighting(self):
        """Update keyboard lighting based on current state"""
        try:
            # Clear keyboard
            for r in range(self.rows):
                for c in range(self.cols):
                    self.razer_keyboard.fx.advanced.matrix[r, c] = (0, 0, 0)
            
            # Apply current mode with fallback
            current_mode = self.get_current_mode()
            mode_config = self.config.get('modes', {}).get(current_mode)
            
            # Fallback to base mode if current mode not defined
            if mode_config is None and current_mode != 'base':
                if self.should_log():
                    print(f"Mode '{current_mode}' not defined, falling back to base")
                mode_config = self.config.get('modes', {}).get('base', {})
            
            # If still no config, use empty
            if mode_config is None:
                mode_config = {}
            
            if self.should_log():
                print(f"Applying lighting for mode: {current_mode}")
            
            # Apply all rules for the current mode
            for rule in mode_config.get('rules', []):
                self.apply_rule(rule)
            
            # Draw changes
            self.razer_keyboard.fx.advanced.draw()
        except Exception as e:
            if self.should_log():
                print(f"Error updating lighting: {e}")
            traceback.print_exc()

    def on_press(self, key):
        """Handle key press events"""
        try:
            key_identifier = self.normalize_key_event(key)
            
            # Track modifiers
            if key in self.modifier_keys:
                mod_name = self.modifier_keys[key]
                self.active_modifiers.add(key)
                # Add modifier to pressed keys if not already present
                if mod_name not in self.pressed_keys:
                    self.pressed_keys.append(mod_name)
                if self.should_log():
                    print(f"Modifier pressed: {mod_name} (active: {[self.modifier_keys[k] for k in self.active_modifiers]})")
            else:
                # Non-modifier
                if self.should_log():
                    print(f"Key pressed: {key_identifier}")
                if key_identifier not in self.pressed_keys:
                    self.pressed_keys.append(key_identifier)
            
            # Update lighting
            self.update_lighting()
            
            # Update workspaces when modifier state changes (only if i3 enabled)
            if self.i3_enabled and key in [Key.cmd, Key.alt]:
                self.update_workspaces()
        except Exception as e:
            if self.should_log():
                print(f"Error in on_press: {e}")

    def on_release(self, key):
        """Handle key release events"""
        try:
            key_identifier = self.normalize_key_event(key)
            
            if key in self.modifier_keys:
                mod_name = self.modifier_keys[key]
                # Remove from active modifiers
                if key in self.active_modifiers:
                    self.active_modifiers.remove(key)
                # Remove from pressed keys
                if mod_name in self.pressed_keys:
                    if self.should_log():
                        print(f"Modifier released: {mod_name} (active: {[self.modifier_keys[k] for k in self.active_modifiers]})")
                    self.pressed_keys.remove(mod_name)
            else:
                if key_identifier in self.pressed_keys:
                    if self.should_log():
                        print(f"Key released: {key_identifier}")
                    self.pressed_keys.remove(key_identifier)
            
            # Update lighting
            self.update_lighting()
            
            # FIX: Maintain current mode if any keys are still pressed
            if self.pressed_keys:
                # Check if we should stay in the current mode
                if self.current_mode != 'base':
                    # If the current mode is based on modifiers and there are still active modifiers, keep it
                    if any(m in self.pressed_keys for m in ['super', 'shift', 'alt', 'ctrl']):
                        return
                    # If the current mode is based on a sequence and there are still pressed keys, keep it
                    if self.current_mode in self.config.get('modes', {}):
                        return
                # Otherwise fall back to base mode
                self.current_mode = 'base'
        except Exception as e:
            if self.should_log():
                print(f"Error in on_release: {e}")

    def start_i3_listener(self):
        """Listen for i3 window events (only if enabled)"""
        if not self.i3_enabled or not I3_AVAILABLE:
            return
            
        try:
            i3 = i3ipc.Connection()
            i3.on('window', self.on_i3_event)
            if self.should_log():
                print("Starting i3 event listener")
            i3.main()
        except Exception as e:
            if self.should_log():
                print(f"Error in i3 listener: {e}")

    def on_i3_event(self, i3, event):
        """Handle i3 window events (only if enabled)"""
        if not self.i3_enabled:
            return
            
        try:
            if event.change in ['new', 'close', 'move']:
                self.update_workspaces()
                self.update_lighting()
        except Exception as e:
            if self.should_log():
                print(f"Error in i3 event handler: {e}")

    def start_pywal_watcher(self):
        """Start watching pywal color file for changes"""
        pywal_path = os.path.expanduser('~/.cache/wal')
        if not os.path.exists(pywal_path):
            os.makedirs(pywal_path, exist_ok=True)
            print(f"Created pywal directory: {pywal_path}")
        
        pywal_event_handler = PywalFileHandler(self.handle_pywal_update)
        self.pywal_watchdog_observer = Observer()
        self.pywal_watchdog_observer.schedule(pywal_event_handler, pywal_path, recursive=False)
        self.pywal_watchdog_observer.start()
        if self.should_log():
            print(f"Started watching pywal colors at {pywal_path}")

    def start_config_watcher(self):
        """Start watching config file for changes"""
        config_path = os.path.expanduser('~/.config/razer-keyboard-highlighter')
        if not os.path.exists(config_path):
            os.makedirs(config_path, exist_ok=True)
            print(f"Created config directory: {config_path}")
        
        config_event_handler = ConfigFileHandler(self.handle_config_update)
        self.config_watchdog_observer = Observer()
        self.config_watchdog_observer.schedule(config_event_handler, config_path, recursive=False)
        self.config_watchdog_observer.start()
        if self.should_log():
            print(f"Started watching config at {config_path}")

    def handle_pywal_update(self):
        """Called when pywal colors change - update lighting"""
        if self.should_log():
            print("Pywal colors updated - reloading")
        self.pywal_updated = True

    def handle_config_update(self):
        """Called when configs change - update lighting"""
        if self.should_log():
            print("Config updated - reloading")
        self.config_updated = True

    def reload_pywal_colors(self):
        """Reload colors and update lighting"""
        with self.colors_lock:
            self.colors = self.load_colors()
        self.pywal_updated = False
        self.update_lighting()
        if self.should_log():
            print("Colors reloaded from pywal")

    def run(self):
        """Main application loop"""
        try:
            if self.i3_enabled:
                self.update_workspaces()
                
                # Start i3 listener thread only if enabled
                self.i3_thread = threading.Thread(target=self.start_i3_listener, daemon=True)
                self.i3_thread.start()
                if self.should_log():
                    print("i3 listener started")
            
            # Start keyboard listener
            self.key_listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            )
            self.key_listener.start()
            if self.should_log():
                print("Keyboard listener started")
            
            # Start pywal file watcher if enabled
            if self.config.get('pywal', True):
                self.start_pywal_watcher()
                if self.should_log():
                    print("Pywal file watcher started")

            self.start_config_watcher()
            if self.should_log():
                print("Config file watcher started")
            
            # Apply initial lighting
            self.update_lighting()
            
            # Main loop
            if self.should_log():
                print("Entering main loop (Press Ctrl+C to exit)")
            while True:
                time.sleep(1)
                # Check for pywal updates
                if self.pywal_updated:
                    self.reload_pywal_colors()
                # Check for config updates
                if self.config_updated:
                    self.reload_config()
                
                # Periodically update workspaces only if enabled
                if self.i3_enabled:
                    self.update_workspaces()
        except KeyboardInterrupt:
            if self.should_log():
                print("Exiting...")
            if self.key_listener:
                self.key_listener.stop()
            if self.pywal_watchdog_observer:
                self.pywal_watchdog_observer.stop()
                self.pywal_watchdog_observer.join()
            if self.config_watchdog_observer:
                self.config_watchdog_observer.stop()
                self.config_watchdog_observer.join()
            # Turn off keyboard lights
            try:
                for r in range(self.rows):
                    for c in range(self.cols):
                        self.razer_keyboard.fx.advanced.matrix[r, c] = (0, 0, 0)
                self.razer_keyboard.fx.advanced.draw()
            except:
                pass
        except Exception as e:
            if self.should_log():
                print(f"Error in main loop: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    try:
        controller = KeyboardController()
        controller.run()
    except Exception as e:
        print(f"Critical error: {e}")
        traceback.print_exc()
