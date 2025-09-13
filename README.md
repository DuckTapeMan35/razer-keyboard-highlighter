# Razer keyboard highlighter

Support for highlighting keys when held according to a configuration file with pywal, i3wm and hyprland integration, supports key combinations of any order/size

## IMPORTANT
I have done my best to secure this application such that keypress events cannot be sniffed by some third party, however, this is still theoritically possible and can be a vulnerability you are introducing in your system if you use wayland, the reason this is not a concern for x11 is because x11 has no protections against keyloggers whereas a keylogger must have sudo permissions on wayland.

## Requirements

### General requirements

- i3wm (optional)
- hyprland (optional)
- pywal (optional)
- python

### Python libraries

- i3ipc (optional)
- keyboard
- watchdog
- pyyaml
- openrazer
- psutil

These libraries should be installed on the side of the user because `razer_controller` needs to run as user (no sudo permissions)

`sudo pacman -S openrazer-daemon python-openrazer i3ipc watchdog pyyaml`

To use openrazer the openrazer daemon must be set up, to do so follow the tutorial here: https://openrazer.github.io/#download

`keyboard` and `psutil` need to installed as root for `keyboard_listener` to function, I recommend you create a venv in `/root/razer_keyboard_highlighter_venv` and install these libraries there

```bash
sudo python -m venv /root/razer_keyboard_highlighter_venv
sudo /root/razer_keyboard_highlighter_venv/bin/pip install --upgrade pip
sudo /root/razer_keyboard_highlighter_venv/bin/pip install keyboard psutil
```

## Setup

Included in this repository is a script that creates a daemon that runs razer_keyboard_highlighter.py on arch linux, if that is your desired way to run this you can do

```bash
git clone https://github.com/DuckTapeMan35/razer-keyboard-highlighter
cd razer-keyboard-highlighter
chmod +x setup.sh
./setup.sh
```

This will create a daemon that listens to your keypresses and writes them to a socket, then you can use the command `razer_controller` to start the application. If you want this to work on startup you need to start it in your window manager's config file (so it starts as a child process of the window manager), otherwise the window manager integrations will not work. If you don't use a window manager/don't want the integrations, you can make a daemon and start/enable it, however, note that `razer_controller` must be run as a user without root permissions and must also run after `keyboard_listener`.

Afterwards simply edit the config file under `.config/keyboard-razer-highlighter/` (where the script will be placed), details on how a proper config file should look below, in this repository there is also my personal config file as an example.

If wish to install this manually note that `razer_controller` must be placed under `/usr/bin/` or the `keyboard_listener` will not accept its attempt at a connection. Note, also that `razer_controller` must always be run after `keyboard_listener`

## Configuration file

The configuration file should be named config.yaml and be placed under `.config/razer-keyboard-highlighter/`

Here is my personal config file that I will be detailing the workings of:

```yaml
pywal: true
window_manager: hyprland
log_level: info

key_positions:
  # Define positions for individual keys, the tuple corrsponds to (row, column) of they keyboard as defioned by openrazer
  q: 
    - (2, 1)
  d: 
    - (3, 3)
  x:
    - (4, 3)
  z: 
    - (4, 2)
  s:
    - (3, 2)
  p:
    - (2, 10)
  v:
    - (4, 5)
  b:
    - (4, 6)
  e:
    - (2, 3)
  1_key:
    - (1,1)
  2_key:
    - (1,2)
  3_key:
    - (1,3)
  4_key:
    - (1,4)
  5_key:
    - (1,5)
  6_key:
    - (1,6)
  7_key:
    - (1,7)
  8_key:
    - (1,8)
  9_key:
    - (1,9)
  10_key:
    - (1,10)
  
  # Define positions for special keys
  super: 
    - (5, 1)
  enter: 
    - (3, 13)
  shift:
    - (4, 0)
  alt:
    - (5, 2)
  space:
    - (5, 6)
  ctrl:
    - (5, 0)

  # Define groups of keys
  numbers:
    - (1, 1)
    - (1, 2)
    - (1, 3)
    - (1, 4)
    - (1, 5)
    - (1, 6)
    - (1, 7)
    - (1, 8)
    - (1, 9)
    - (1, 10)
  arrows:
    - (5, 14)
    - (5, 15)
    - (5, 16)
    - (4, 15)

modes:
  # Base mode - applied when no keys are pressed
  base:
    rules:
      - keys: [all]
        color: color[1]
      - keys: [numbers]
        condition: non_empty_workspaces
        value: false
        color: color[3]
      - keys: [numbers]
        condition: non_empty_workspaces
        value: true
        color: color[7]

  # Single-key modes
  super:
    rules:
      - keys: [numbers]
        condition: non_empty_workspaces
        value: false
        color: color[3]
      - keys: [numbers]
        condition: non_empty_workspaces
        value: true
        color: color[7]
      - keys: [super]
        color: [255, 255, 255]
      - keys: [enter]
        color: color[7]
      - keys: [d]
        color: color[2] 
      - keys: [x]
        color: [255, 0, 0]
      - keys: [z]
        color: color[3]
      - keys: [v]
        color: color[4]
      - keys: [b]
        color: color[5]
      - keys: [arrows]
        color: color[1]
      - keys: [shift]
        color: [255, 255, 255]
      - keys: [e]
        color: color[6]

  # Two-key combination modes are formated as KeyBeingHeld_NewKeyBeingHeld
  super_shift:
    rules:
      - keys: [numbers]
        condition: non_empty_workspaces
        value: false
        color: color[3]
      - keys: [numbers]
        condition: non_empty_workspaces
        value: true
        color: color[7]
      - keys: [super]
        color: [255, 255, 255]
      - keys: [q]
        color: [255, 0, 0]
      - keys: [shift]
        color: [255, 255, 255]
      - keys: [arrows]
        color: color[1]
      - keys: [s]
        color: color[1]
      - keys: [p]
        color: color[3]
      - keys: [space]
        color: color[4]

  # modes are order dependant so if you want both orders to work you need to replicate them and reverse the order here
  shift_super:
    rules:
      - keys: [numbers]
        condition: non_empty_workspaces
        value: false
        color: color[3]
      - keys: [numbers]
        condition: non_empty_workspaces
        value: true
        color: color[7]
      - keys: [super]
        color: [255, 255, 255]
      - keys: [q]
        color: [255, 0, 0]
      - keys: [shift]
        color: [255, 255, 255]
      - keys: [arrows]
        color: color[1]
      - keys: [s]
        color: color[1]
      - keys: [p]
        color: color[3]
      - keys: [space]
        color: color[4]

  alt:
    rules:
      - keys: [1_key]
        color: [188,214,160]
      - keys: [2_key]
        color: [143,143,144]
      - keys: [3_key]
        color: [99,146,152]
      - keys: [4_key]
        color: [57,99,88]
      - keys: [5_key]
        color: [173,74,44]
      - keys: [6_key]
        color: [146,120,150]
      - keys: [7_key]
        color: [93,185,213]
      - keys: [8_key]
        color: [38,52,115]
      - keys: [9_key]
        color: [43,86,138]
      - keys: [10_key]
        color: [131,97,130]
      - keys: [alt]
        color: [255,255,255]

  ctrl_alt:
    rules:
      - keys: [s]
        color: color[1]
      - keys: [alt]
        color: [255,255,255]
      - keys: [ctrl]
        color: [255,255,255]

  alt_ctrl:
    rules:
      - keys: [s]
        color: color[1]
      - keys: [alt]
        color: [255,255,255]
      - keys: [ctrl]
        color: [255,255,255]
```

### Pywal
`pywal: true/false`, will determine wether or not pywal will be integrated.

### window_manager

`window_manager: i3/hyprland` determines wether or not i3/hyprland integration is needed, however if rules that need i3/hyprland integration are present on the config, even if it is omitted rules will be applied

### Log

The line `log_level: debug/info/warning/error/critical` sets the level, by default `log_level` is `info`. 

### Key positions

Key positions follow the structure of

```yaml
key_positions:
  key_name: 
    - (2, 1)
```

key_name can be anything and the tuple corresponds to the (row, column) of the key as defined by openrazer. It is also possible to define a key as having several positions, that is, a key group. rules applied to a key group will apply to all keys in said group. Rules will be discussed shortly.

### Modes

#### Base

The base mode is of special importance, it represents what happens when no valid key combos are held, I recommend setting this to a single solid color or a solid color with workspaces. The reason why I don't support animations is because they have a fade-in effect, that is a quirk of the openrazer api and I can't do anything about it. Perhaps at a later date this feature will be added.

#### Keys and Rules

- Single keys

Single keys follow the structure of:

```yaml
KeyHeld:
    rules:
      - keys: [key_name]
        condition: non_empty_workspaces
        value: true/false
        color: color[pywal_color_numeber] or [R,G,B]
```

For now the only condition is non_empty_workspaces, for it to work the workspaces must be renamed to numbers (1-10) and it can only be applied to numbers.

As an example if key_name is 6 and it's position corresponds to the 6 key on the keyboard and the value of the condition is true the key will be lit up with the given color if there is a window open on the workspace, if the value is false then it will be lit up with the provided color if there are no windows in the corresponding workspace.

- n keys

n keys refers to when n keys are being held together, they follow the structure of FirstKeyHeld_SecondKeyHeld_etc . As an example let's take super_shift, this mode and its rules will only trigger when first super is held and then shift is held.

Note: if you don't care about order you need to add both super_shift and shift_super with the same rules.
