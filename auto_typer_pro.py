import pyautogui
import time
import random
import threading
import sys
import platform
import re
import pygame
from pynput.keyboard import GlobalHotKeys

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================

# -- Keyboard Hotkeys --
HOTKEY_START_SEQUENCE = '<f12>' 
HOTKEY_PAUSE_RESUME = '<ctrl>+<alt>+p'
HOTKEY_QUIT = '<ctrl>+<alt>+q'

# -- Live Speed Control Hotkeys --
HOTKEY_SPEED_UP = '<up>'    # Keyboard Up Arrow
HOTKEY_SPEED_DOWN = '<down>'  # Keyboard Down Arrow

# -- Game Controller Buttons --
BUTTON_START_SEQUENCE = 1  
BUTTON_PAUSE_RESUME = 8    
BUTTON_QUIT = 5            

# -- Gamepad Speed Control (D-Pad/Hat) --
HAT_SPEED_UP = (0, 1)      # D-Pad Up
HAT_SPEED_DOWN = (0, -1)   # D-Pad Down

# -- Director Mode Config --
PLAN_START_TAG = "#<--PLAN-->"
PLAN_END_TAG = "#<--END-PLAN-->"
BLOCK_START_REGEX = r'#<--BLOCK:\s*(.+?)-->' 
VSCODE_DELETE_LINE_HOTKEY = ('ctrl', 'shift', 'k') 

# -- Typing Speed & Simulation --
BASE_SPEED_SECONDS = 0.12
MIN_SPEED = 0.02
MAX_SPEED = 0.5
SPEED_STEP = 0.02
HUMANLIKE_RANDOMNESS = 0.4
TYPO_CHANCE = 0.02
TYPO_FIX_PAUSE = 0.3
THINKING_CHARS = ['\n', ':', '{', '}']
THINKING_PAUSE_DURATION = 0.8

# ==============================================================================
# --- SCRIPT LOGIC ---
# ==============================================================================

# --- Global State Variables ---
plan_steps = []              
code_blocks = {}             
start_signal = threading.Event() 
is_paused = False            
script_running = True        
hotkey_listener = None       
gamepad_listener_thread = None 
g_base_speed = BASE_SPEED_SECONDS 
g_current_line = 1 # We always start at line 1

# --- Core Command Functions (Called by background threads) ---

def start_typing_sequence():
    """Signals the main thread to start typing OR resume from a plan pause."""
    if not start_signal.is_set():
        print(f"[STARTED] Start signal received! Main thread will begin typing.")
        start_signal.set() 
    else:
        print("[INFO] Signal already set. Typing is likely running or will resume.")

def toggle_pause():
    """Toggles the 'is_paused' flag."""
    global is_paused
    is_paused = not is_paused
    if is_paused:
        print("\n[PAUSED] Typing is paused. Press hotkey/button again to resume.")
    else:
        print("\n[RESUMED] Typing will continue...")

def stop_script():
    """Sets all flags to gracefully stop the script."""
    global script_running, hotkey_listener, is_paused
    print("\n[STOPPING] Script will terminate...")
    script_running = False
    is_paused = False 
    start_signal.set() 
    
    if hotkey_listener:
        hotkey_listener.stop()
    pygame.quit() 

# --- Live Speed Control Functions ---
def speed_up():
    global g_base_speed
    g_base_speed = max(MIN_SPEED, g_base_speed - SPEED_STEP)
    print(f"[SPEED] Typing speed increased to: {g_base_speed:.2f}s")

def speed_down():
    global g_base_speed
    g_base_speed = min(MAX_SPEED, g_base_speed + SPEED_STEP)
    print(f"[SPEED] Typing speed decreased to: {g_base_speed:.2f}s")

# --- NEW: Cursor Navigation Function ---
def move_cursor_to_line(target_line):
    """Realistically moves the cursor using arrow keys."""
    global g_current_line
    
    move = target_line - g_current_line
    
    if move > 0:
        print(f"Moving cursor down {move} lines...")
        for _ in range(move):
            pyautogui.press('down')
            g_current_line += 1 # Update memory as we move
    elif move < 0:
        print(f"Moving cursor up {abs(move)} lines...")
        for _ in range(abs(move)):
            pyautogui.press('up')
            g_current_line -= 1 # Update memory as we move
    
    # Always go to the start of the line
    pyautogui.press('home')
    time.sleep(0.3) # Small pause after moving

# --- Typing Logic (Called by the MAIN THREAD) ---
def do_typing_sequence():
    """This function types all blocks as defined in the PLAN."""
    global is_paused, script_running, start_signal, g_current_line
    
    time.sleep(0.5) 

    for step_num, step in enumerate(plan_steps, 1):
        if not script_running: break
        
        while is_paused:
            if not script_running: break
            time.sleep(0.1)
        
        print(f"\n--- Step {step_num} of {len(plan_steps)} ---")
        
        step_type = step[0]
        
        if step_type == 'TYPE':
            # step = ('TYPE', line_num, block_name)
            line_num, block_name = step[1], step[2]
            
            move_cursor_to_line(line_num)
            
            if block_name not in code_blocks:
                print(f"[ERROR] Block '{block_name}' not found in library. Skipping step.")
                continue
            
            # --- BUG FIX #1: Remove .strip() to preserve indentation ---
            code_to_type = code_blocks[block_name]
            print(f"Calling block '{block_name}'...")
            
            for char in code_to_type:
                while is_paused: 
                    if not script_running: break
                    time.sleep(0.1) 
                if not script_running: break

                if random.random() < TYPO_CHANCE and char.isalpha():
                    typo = get_adjacent_key(char)
                    pyautogui.write(typo)
                    time.sleep(TYPO_FIX_PAUSE)
                    pyautogui.press('backspace')
                    time.sleep(TYPO_FIX_PAUSE / 2)

                pyautogui.write(char)

                if char in THINKING_CHARS:
                    pause_duration = random.uniform(THINKING_PAUSE_DURATION * 0.7, THINKING_PAUSE_DURATION * 1.3)
                    time.sleep(pause_duration)
                else:
                    delay = random.uniform(g_base_speed * (1 - HUMANLIKE_RANDOMNESS),
                                           g_base_speed * (1 + HUMANLIKE_RANDOMNESS))
                    time.sleep(delay)
            
            # --- BUG FIX #2: Update memory based on lines typed ---
            # Count the newlines in the block just typed
            num_newlines = code_to_type.count('\n')
            g_current_line += num_newlines # Add to our current line
            print(f"[DEBUG] Cursor is now on line: {g_current_line}")


        elif step_type == 'WAIT':
            # step = ('WAIT', duration)
            duration = step[1]
            print(f"Waiting for {duration} seconds...")
            time.sleep(duration)

        elif step_type == 'DELETE':
            # step = ('DELETE', line_num)
            line_num = step[1]
            
            print(f"Moving to line {line_num} to delete it...")
            move_cursor_to_line(line_num)
            pyautogui.hotkey(*VSCODE_DELETE_LINE_HOTKEY)
            # Deleting a line moves the cursor, but we stay on the "same" line number
            # So g_current_line does not need to change

        elif step_type == 'PAUSE_INPUT':
            # step = ('PAUSE_INPUT', )
            print("\n[PLAN PAUSED] Plan is paused. Press 'Start' hotkey to continue.")
            start_signal.clear() 
            start_signal.wait()  
            if script_running:
                print("[PLAN RESUMED] Resuming plan...")
        
        time.sleep(THINKING_PAUSE_DURATION) 

    if script_running:
        print("\n--- Typing Sequence Complete! ---")
    else:
        print("\n--- Typing terminated by user ---")
    
    stop_script() 

# --- Controller Listener (Runs in its own thread) ---
def listen_for_gamepad():
    """Pygame event loop to listen for controller buttons."""
    global script_running
    
    try:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            controller = pygame.joystick.Joystick(0)
            controller.init()
            print(f"[INFO] Game controller '{controller.get_name()}' connected.")
        else:
            print("[WARNING] No game controller found. Only keyboard hotkeys will be active.")
            return
    except Exception as e:
        print(f"[WARNING] Failed to initialize game controller: {e}. Only keyboard hotkeys will be active.")
        return
        
    print("[INFO] Game controller listener started.")
    last_button_state = {} 
    
    while script_running:
        try:
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    if not last_button_state.get(event.button, False): 
                        last_button_state[event.button] = True
                        if event.button == BUTTON_START_SEQUENCE:
                            start_typing_sequence()
                        elif event.button == BUTTON_PAUSE_RESUME:
                            toggle_pause()
                        elif event.button == BUTTON_QUIT:
                            stop_script()
                            
                elif event.type == pygame.JOYBUTTONUP:
                    last_button_state[event.button] = False
                
                elif event.type == pygame.JOYHATMOTION:
                    hat_val = event.value 
                    if hat_val == HAT_SPEED_UP:
                        speed_up()
                    elif hat_val == HAT_SPEED_DOWN:
                        speed_down()

            time.sleep(0.01) 
        except Exception as e:
            if script_running: 
                print(f"[ERROR] Gamepad listener failed: {e}")
            break
    print("[INFO] Game controller listener stopped.")


# --- Helper Functions ---
def get_adjacent_key(key):
    key = key.lower()
    key_map = { 'q': ['w', 'a'], 'w': ['q', 's', 'e'], 'e': ['w', 'd', 'r'], 'a': ['q', 's', 'z'], 's': ['a', 'w', 'd', 'z'], 'd': ['s', 'e', 'f', 'x'], 'o': ['i', 'p', 'l'], 'l': ['k', 'o', ';'], 'm': ['n', 'k', ','] }
    return random.choice(key_map.get(key, ['a', 's', 'e', 'i', 'o']))

def check_os_permissions():
    os_name = platform.system()
    if os_name == 'Darwin': # macOS
        print("\n--- macOS User Notice ---")
        print("For this script to work, you MUST grant Accessibility permissions.")
        print("Go to: System Settings > Privacy & Security > Accessibility.")
        print("-------------------------\n")

def load_code_from_file():
    global plan_steps, code_blocks
    try:
        with open('code.txt', 'r', encoding='utf-8') as f:
            full_code = f.read()
    except FileNotFoundError:
        print("Error: 'code.txt' not found! Please create it and add your code.")
        sys.exit(1)
        
    # 1. Parse the PLAN
    try:
        plan_regex = re.search(f"{PLAN_START_TAG}(.*?){PLAN_END_TAG}", full_code, re.DOTALL)
        if not plan_regex:
            print("[ERROR] No #<--PLAN--> section found in code.txt. Exiting.")
            sys.exit(1)
        
        plan_content = plan_regex.group(1)
        plan_lines = [line.strip() for line in plan_content.splitlines() if line.strip()]
        
        for line in plan_lines:
            match_type = re.search(r'AT_LINE:\s*(\d+)\s*,\s*CALL_BLOCK:\s*"(.+?)"', line, re.I)
            match_wait = re.search(r'WAIT:\s*([\d.]+)', line, re.I)
            match_delete = re.search(r'DELETE_LINE:\s*(\d+)', line, re.I)
            match_pause = re.search(r'PAUSE_FOR_INPUT', line, re.I)

            if match_type:
                plan_steps.append(('TYPE', int(match_type.group(1)), match_type.group(2)))
            elif match_wait:
                plan_steps.append(('WAIT', float(match_wait.group(1))))
            elif match_delete:
                plan_steps.append(('DELETE', int(match_delete.group(1))))
            elif match_pause:
                plan_steps.append(('PAUSE_INPUT',))
        
        print(f"[INFO] Loaded {len(plan_steps)} steps from the PLAN.")
        if not plan_steps:
             print("[WARNING] 0 steps loaded. Check your PLAN syntax in code.txt.")
        
    except Exception as e:
        print(f"[ERROR] Failed to parse the PLAN in code.txt: {e}")
        sys.exit(1)
        
    # 2. Parse the BLOCKS
    try:
        parts = re.split(BLOCK_START_REGEX, full_code)
        if len(parts) < 3:
             print("[ERROR] No #<--BLOCK: ...--> tags found in code.txt. Exiting.")
             sys.exit(1)
             
        for i in range(1, len(parts), 2):
            block_name = parts[i].strip()
            # --- BUG FIX #1 (Load): Don't strip() the code block itself ---
            block_code = parts[i+1].replace('\t', ' ' * 4) # Normalize tabs
            code_blocks[block_name] = block_code
        
        print(f"[INFO] Loaded {len(code_blocks)} code blocks from the library.")
            
    except Exception as e:
        print(f"[ERROR] Failed to parse the BLOCKS in code.txt: {e}")
        sys.exit(1)

# --- Main Execution Block ---
if __name__ == "__main__":
    check_os_permissions()
    load_code_from_file()

    try:
        with open('script.txt', 'r', encoding='utf-8') as f:
            print("\n--- Voice-Over Script (for reference) ---")
            print(f.read())
            print("------------------------------------------")
    except FileNotFoundError:
        print("\nInfo: 'script.txt' not found. You can create it for your voice-over notes.")

    # 1. Start the Game Controller Listener Thread
    gamepad_listener_thread = threading.Thread(target=listen_for_gamepad, daemon=True)
    gamepad_listener_thread.start()

    # 2. Define Keyboard Hotkeys
    hotkey_bindings = {
        HOTKEY_START_SEQUENCE: start_typing_sequence,
        HOTKEY_PAUSE_RESUME: toggle_pause,
        HOTKEY_QUIT: stop_script,
        HOTKEY_SPEED_UP: speed_up,
        HOTKEY_SPEED_DOWN: speed_down
    }

    print("\n--- Director Mode Auto-Typer v3.1 (Fixed Memory) ---")
    print(f"  Press '{HOTKEY_START_SEQUENCE}' or Controller Button {BUTTON_START_SEQUENCE} to START.")
    print(f"  Press '{HOTKEY_PAUSE_RESUME}' or Controller Button {BUTTON_PAUSE_RESUME} to Pause/Resume.")
    print(f"  Press '{HOTKEY_QUIT}' or Controller Button {BUTTON_QUIT} to Quit.")
    print(f"\n  Press '{HOTKEY_SPEED_UP}' or D-Pad Up to Type Faster.")
    print(f"  Press '{HOTKEY_SPEED_DOWN}' or D-Pad Down to Type Slower.")
    print("-------------------------------------------------")
    print("Waiting for start signal...")

    # 3. Start Keyboard Listener
    hotkey_listener = GlobalHotKeys(hotkey_bindings)
    hotkey_listener.start()

    # 4. Main thread waits for start signal
    start_signal.wait()

    if script_running:
        do_typing_sequence()

    # 5. Clean up
    print("Script has finished. Exiting.")