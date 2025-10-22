import pyautogui
import time
import random
import threading
import sys
import platform
import re
import pygame
from pynput.keyboard import GlobalHotKeys
import tkinter as tk # Added for subtitle display

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================

# -- Keyboard Hotkeys --
HOTKEY_START_SEQUENCE = '<f12>'
HOTKEY_PAUSE_RESUME = '<ctrl>+<alt>+p'
HOTKEY_QUIT = '<ctrl>+<alt>+q'
HOTKEY_SPEED_UP = '<up>'
HOTKEY_SPEED_DOWN = '<down>'
HOTKEY_TOGGLE_SUBTITLES = '<ctrl>+<alt>+t'

# -- Game Controller Buttons --
BUTTON_START_SEQUENCE = 1
BUTTON_PAUSE_RESUME = 8
BUTTON_QUIT = 5
BUTTON_TOGGLE_SUBTITLES = 6

# -- Gamepad Speed Control (D-Pad/Hat) --
HAT_SPEED_UP = (0, 1)
HAT_SPEED_DOWN = (0, -1)

# -- Director Mode Config --
PLAN_START_TAG = "#<--PLAN-->"
PLAN_END_TAG = "#<--END-PLAN-->"
BLOCK_START_REGEX = r'#<--BLOCK:\s*(.+?)-->'
SUBTITLE_TAG_REGEX = r'#<--SUBTITLE:\s*(.+?)-->'
VSCODE_DELETE_LINE_HOTKEY = ('ctrl', 'shift', 'k')

# -- Typing Speed & Simulation --
BASE_SPEED_SECONDS = 0.12
COMMENT_WPM = 125
COMMENT_SPEED_SECONDS = 60 / (COMMENT_WPM * 5.5)
MIN_SPEED = 0.02
MAX_SPEED = 0.5
SPEED_STEP = 0.02
HUMANLIKE_RANDOMNESS = 0.4
TYPO_CHANCE = 0.01
TYPO_FIX_PAUSE = 0.3
THINKING_CHARS = [':', '{', '}']
THINKING_PAUSE_DURATION = 0.6

# -- Subtitle Window Config --
SUBTITLE_WINDOW_WIDTH = 800
SUBTITLE_WINDOW_HEIGHT = 100
SUBTITLE_FONT_SIZE = 16
SUBTITLE_BG_COLOR = "#222222"
SUBTITLE_FG_COLOR = "#FFFFFF"

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
g_current_line = 1
subtitles_enabled = True
subtitle_window = None
subtitle_label = None

# --- Core Command Functions ---
def start_typing_sequence():
    if not start_signal.is_set():
        print(f"[STARTED] Start signal received! Main thread will begin typing.")
        start_signal.set()
    else:
        print("[INFO] Signal already set. Typing is likely running or will resume.")

def toggle_pause():
    global is_paused
    is_paused = not is_paused
    if is_paused:
        update_subtitle("--- PAUSED ---")
        print("\n[PAUSED] Typing is paused. Press hotkey/button again to resume.")
    else:
        update_subtitle("")
        print("\n[RESUMED] Typing will continue...")

def stop_script():
    """Sets all flags to gracefully stop the script."""
    global script_running, hotkey_listener, is_paused
    # --- THIS IS THE FIX ---
    global subtitle_window 
    # -----------------------
    print("\n[STOPPING] Script will terminate...")
    script_running = False
    is_paused = False # Release any pause-loops
    start_signal.set() # Wake up the main thread so it can exit

    if hotkey_listener:
        hotkey_listener.stop()
    pygame.quit() # Stop the pygame engine
    if subtitle_window: # <-- This check will now work
        try:
            # Safely schedule the window destruction from the Tkinter thread
            subtitle_window.after(0, subtitle_window.destroy)
        except tk.TclError: # Handle cases where window might already be closing
            pass
        subtitle_window = None # Clear references immediately

def speed_up():
    global g_base_speed
    g_base_speed = max(MIN_SPEED, g_base_speed - SPEED_STEP)
    print(f"[SPEED] Typing speed increased to: {g_base_speed:.2f}s")
    update_subtitle(f"Speed: {g_base_speed:.2f}s")

def speed_down():
    global g_base_speed
    g_base_speed = min(MAX_SPEED, g_base_speed + SPEED_STEP)
    print(f"[SPEED] Typing speed decreased to: {g_base_speed:.2f}s")
    update_subtitle(f"Speed: {g_base_speed:.2f}s")

def toggle_subtitles():
    global subtitles_enabled
    subtitles_enabled = not subtitles_enabled
    if subtitles_enabled:
        print("[SUBTITLES] Subtitles ENABLED")
        update_subtitle("Subtitles ON")
    else:
        print("[SUBTITLES] Subtitles DISABLED")
        update_subtitle("Subtitles OFF")

# --- Subtitle Window Functions ---
def create_subtitle_window():
    global subtitle_window, subtitle_label

    def run_tk():
        global subtitle_window, subtitle_label
        root = None # Define root here to ensure it's accessible in finally
        try:
            root = tk.Tk()
            root.withdraw()

            subtitle_window = tk.Toplevel(root)
            subtitle_window.overrideredirect(True)
            subtitle_window.wm_attributes("-topmost", True)
            subtitle_window.configure(bg=SUBTITLE_BG_COLOR)

            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width // 2) - (SUBTITLE_WINDOW_WIDTH // 2)
            y = screen_height - SUBTITLE_WINDOW_HEIGHT - 50
            subtitle_window.geometry(f"{SUBTITLE_WINDOW_WIDTH}x{SUBTITLE_WINDOW_HEIGHT}+{x}+{y}")

            subtitle_label = tk.Label(
                subtitle_window,
                text="Subtitles Initializing...",
                font=("Arial", SUBTITLE_FONT_SIZE),
                fg=SUBTITLE_FG_COLOR,
                bg=SUBTITLE_BG_COLOR,
                wraplength=SUBTITLE_WINDOW_WIDTH - 20
            )
            subtitle_label.pack(expand=True, fill="both", padx=10, pady=10)

            print("[INFO] Subtitle window created.")
            root.mainloop() # Start the Tkinter event loop

        except Exception as e:
            print(f"[ERROR] Subtitle window crashed: {e}")
        finally:
            print("[INFO] Tkinter thread exiting.")
            # Clear references when the loop ends or crashes
            subtitle_window = None
            subtitle_label = None
            if root: # Attempt to destroy root if it exists
                try:
                    root.quit()
                except: pass


    tk_thread = threading.Thread(target=run_tk, daemon=True)
    tk_thread.start()

def update_subtitle(text=""):
    """Safely updates the text in the subtitle label."""
    # --- BUG FIX: Check if window and label exist ---
    if subtitle_window and subtitle_label:
        try:
            # Determine text based on enabled state
            display_text = ""
            if subtitles_enabled:
                 display_text = text
            elif text in ["Subtitles OFF", "--- PAUSED ---", "--- SEQUENCE COMPLETE ---"]: # Show status messages even if off
                 display_text = text

            # Use after() to schedule the update in the Tkinter thread
            subtitle_window.after(0, lambda: subtitle_label.config(text=display_text))
        except tk.TclError:
            # Handle error if window is destroyed mid-update
            pass
        except Exception as e:
            print(f"[ERROR] Failed to update subtitle: {e}")


# --- Cursor Navigation Function ---
def move_cursor_to_line(target_line):
    global g_current_line
    move = target_line - g_current_line
    key_to_press = ''
    count = 0

    if move > 0:
        key_to_press = 'down'
        count = move
        print(f"Moving cursor down {count} lines...")
    elif move < 0:
        key_to_press = 'up'
        count = abs(move)
        print(f"Moving cursor up {count} lines...")

    if key_to_press:
       for _ in range(count):
            pyautogui.press(key_to_press)
            g_current_line += 1 if key_to_press == 'down' else -1
            time.sleep(0.01)

    pyautogui.press('home')
    print(f"[DEBUG] Cursor is now on line: {g_current_line}")
    time.sleep(0.3)

# --- Typing Logic ---
def do_typing_sequence():
    global is_paused, script_running, start_signal, g_current_line
    time.sleep(0.5)
    in_multiline_comment = False

    for step_num, step in enumerate(plan_steps, 1):
        if not script_running: break

        while is_paused:
            if not script_running: break
            time.sleep(0.1)

        print(f"\n--- Step {step_num} of {len(plan_steps)} ---")
        step_type = step[0]

        if step_type == 'TYPE':
            line_num, block_name = step[1], step[2]
            move_cursor_to_line(line_num)

            if block_name not in code_blocks:
                print(f"[ERROR] Block '{block_name}' not found. Skipping.")
                continue

            block_data = code_blocks[block_name]
            code_to_type = block_data['code']
            subtitle_text = block_data['subtitle']

            update_subtitle(subtitle_text)
            print(f"Calling block '{block_name}'...")
            current_line_content_approx = "" # Approximate line content

            for char in code_to_type:
                while is_paused:
                    if not script_running: break
                    time.sleep(0.1)
                if not script_running: break

                # --- Simplified Comment Speed Logic ---
                is_comment_char = False
                if char == '#':
                    is_comment_char = True # Start of single line comment for this char
                elif current_line_content_approx.lstrip().startswith('#'):
                    is_comment_char = True # Already in single line comment
                elif '"""' in current_line_content_approx or "'''" in current_line_content_approx:
                    # Basic check for being inside multiline based on approx content
                    if current_line_content_approx.count('"""') % 2 != 0 or current_line_content_approx.count("'''") % 2 != 0:
                         in_multiline_comment = True
                         is_comment_char = True
                    else:
                         in_multiline_comment = False # Just closed multiline

                current_speed = COMMENT_SPEED_SECONDS if is_comment_char or in_multiline_comment else g_base_speed
                # --- End Comment Speed Logic ---

                if char == '\n':
                    pyautogui.press('enter')
                    g_current_line += 1
                    current_line_content_approx = "" # Reset line approx content
                    # If the multiline start/end was the last thing on the line, reset state
                    if in_multiline_comment and (code_to_type.endswith('"""') or code_to_type.endswith("'''")):
                         in_multiline_comment = False

                else:
                    pyautogui.write(char)
                    current_line_content_approx += char # Add char to approx content
                    # Update multiline state if quotes typed mid-line
                    if '"""' in current_line_content_approx or "'''" in current_line_content_approx:
                         if current_line_content_approx.count('"""') % 2 != 0 or current_line_content_approx.count("'''") % 2 != 0:
                              in_multiline_comment = True
                         else: # Just closed if count is now even
                              in_multiline_comment = False

                if not (is_comment_char or in_multiline_comment) and char != '\n' and random.random() < TYPO_CHANCE and char.isalpha():
                    typo = get_adjacent_key(char)
                    pyautogui.write(typo)
                    time.sleep(TYPO_FIX_PAUSE)
                    pyautogui.press('backspace')
                    time.sleep(TYPO_FIX_PAUSE / 2)

                if char in THINKING_CHARS:
                    pause_duration = random.uniform(THINKING_PAUSE_DURATION * 0.7, THINKING_PAUSE_DURATION * 1.3)
                    time.sleep(pause_duration)
                elif char != '\n':
                    delay = random.uniform(current_speed * (1 - HUMANLIKE_RANDOMNESS),
                                           current_speed * (1 + HUMANLIKE_RANDOMNESS))
                    time.sleep(delay)

            print(f"[DEBUG] Finished block. Cursor approx line: {g_current_line}")

        elif step_type == 'WAIT':
            duration = step[1]
            print(f"Waiting for {duration} seconds...")
            update_subtitle(f"(Waiting {duration}s...)")
            time.sleep(duration)
            update_subtitle("")

        elif step_type == 'DELETE':
            line_num = step[1]
            update_subtitle(f"(Deleting line {line_num}...)")
            print(f"Moving to line {line_num} to delete it...")
            move_cursor_to_line(line_num)
            pyautogui.hotkey(*VSCODE_DELETE_LINE_HOTKEY)
            update_subtitle("")

        elif step_type == 'PAUSE_INPUT':
            print("\n[PLAN PAUSED] Plan is paused. Press 'Start' hotkey/button to continue.")
            update_subtitle("--- PLAN PAUSED --- Press Start to continue ---")
            start_signal.clear()
            start_signal.wait()
            if script_running:
                print("[PLAN RESUMED] Resuming plan...")
                update_subtitle("Resuming plan...")

        if step_type != 'WAIT':
             time.sleep(THINKING_PAUSE_DURATION)

    update_subtitle("--- SEQUENCE COMPLETE ---")
    if script_running:
        print("\n--- Typing Sequence Complete! ---")
    else:
        print("\n--- Typing terminated by user ---")

    stop_script()

# --- Controller Listener ---
def listen_for_gamepad():
    global script_running
    try:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            controller = pygame.joystick.Joystick(0)
            controller.init()
            print(f"[INFO] Game controller '{controller.get_name()}' connected.")
        else:
            print("[WARNING] No game controller found.")
            return
    except Exception as e:
        print(f"[WARNING] Failed to initialize game controller: {e}.")
        return

    print("[INFO] Game controller listener started.")
    last_button_state = {}

    while script_running:
        try:
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    if not last_button_state.get(event.button, False):
                        last_button_state[event.button] = True
                        if event.button == BUTTON_START_SEQUENCE: start_typing_sequence()
                        elif event.button == BUTTON_PAUSE_RESUME: toggle_pause()
                        elif event.button == BUTTON_QUIT: stop_script()
                        elif event.button == BUTTON_TOGGLE_SUBTITLES: toggle_subtitles()

                elif event.type == pygame.JOYBUTTONUP:
                    last_button_state[event.button] = False

                elif event.type == pygame.JOYHATMOTION:
                    hat_val = event.value
                    if hat_val == HAT_SPEED_UP: speed_up()
                    elif hat_val == HAT_SPEED_DOWN: speed_down()

            time.sleep(0.01)
        except Exception as e:
            if script_running: print(f"[ERROR] Gamepad listener failed: {e}")
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
        print("Error: 'code.txt' not found!")
        sys.exit(1)

    # 1. Parse the PLAN
    try:
        plan_regex = re.search(f"{PLAN_START_TAG}(.*?){PLAN_END_TAG}", full_code, re.DOTALL)
        if not plan_regex: raise ValueError("PLAN section not found")
        plan_content = plan_regex.group(1)
        plan_lines = [line.strip() for line in plan_content.splitlines() if line.strip()]
        for line in plan_lines:
            match_type = re.search(r'AT_LINE:\s*(\d+)\s*,\s*CALL_BLOCK:\s*"(.+?)"', line, re.I)
            match_wait = re.search(r'WAIT:\s*([\d.]+)', line, re.I)
            match_delete = re.search(r'DELETE_LINE:\s*(\d+)', line, re.I)
            match_pause = re.search(r'PAUSE_FOR_INPUT', line, re.I)
            if match_type: plan_steps.append(('TYPE', int(match_type.group(1)), match_type.group(2)))
            elif match_wait: plan_steps.append(('WAIT', float(match_wait.group(1))))
            elif match_delete: plan_steps.append(('DELETE', int(match_delete.group(1))))
            elif match_pause: plan_steps.append(('PAUSE_INPUT',))
        print(f"[INFO] Loaded {len(plan_steps)} steps from PLAN.")
        if not plan_steps: print("[WARNING] 0 steps loaded.")
    except Exception as e:
        print(f"[ERROR] Failed to parse PLAN: {e}")
        sys.exit(1)

    # 2. Parse the BLOCKS
    try:
        parts = re.split(BLOCK_START_REGEX, full_code)
        if len(parts) < 3: raise ValueError("No BLOCKS found")
        for i in range(1, len(parts), 2):
            block_name = parts[i].strip()
            block_content = parts[i+1]
            subtitle_match = re.search(SUBTITLE_TAG_REGEX, block_content, re.IGNORECASE)
            subtitle = subtitle_match.group(1).strip() if subtitle_match else ""
            code = re.sub(SUBTITLE_TAG_REGEX, '', block_content, flags=re.IGNORECASE)
            code = code.replace('\t', ' ' * 4)
            if code.startswith('\n'): code = code[1:]
            code_blocks[block_name] = {'code': code, 'subtitle': subtitle}
        print(f"[INFO] Loaded {len(code_blocks)} code blocks from library.")
    except Exception as e:
        print(f"[ERROR] Failed to parse BLOCKS: {e}")
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
        print("\nInfo: 'script.txt' not found.")

    # 1. Start the Subtitle Window
    create_subtitle_window()
    time.sleep(1) # Give Tkinter a moment

    # 2. Start the Game Controller Listener
    gamepad_listener_thread = threading.Thread(target=listen_for_gamepad, daemon=True)
    gamepad_listener_thread.start()

    # 3. Define Keyboard Hotkeys
    hotkey_bindings = {
        HOTKEY_START_SEQUENCE: start_typing_sequence,
        HOTKEY_PAUSE_RESUME: toggle_pause,
        HOTKEY_QUIT: stop_script,
        HOTKEY_SPEED_UP: speed_up,
        HOTKEY_SPEED_DOWN: speed_down,
        HOTKEY_TOGGLE_SUBTITLES: toggle_subtitles
    }

    print("\n--- Director Mode Auto-Typer v4.1 (Final Fixes) ---")
    print(f"  Press '{HOTKEY_START_SEQUENCE}' or Controller Button {BUTTON_START_SEQUENCE} to START.")
    print(f"  Press '{HOTKEY_PAUSE_RESUME}' or Controller Button {BUTTON_PAUSE_RESUME} to Pause/Resume.")
    print(f"  Press '{HOTKEY_QUIT}' or Controller Button {BUTTON_QUIT} to Quit.")
    print(f"  Press '{HOTKEY_TOGGLE_SUBTITLES}' or Controller Button {BUTTON_TOGGLE_SUBTITLES} to Toggle Subtitles.")
    print(f"\n  Press '{HOTKEY_SPEED_UP}' or D-Pad Up to Type Faster.")
    print(f"  Press '{HOTKEY_SPEED_DOWN}' or D-Pad Down to Type Slower.")
    print("-------------------------------------------------")
    print("Waiting for start signal...")

    # 4. Start Keyboard Listener
    hotkey_listener = GlobalHotKeys(hotkey_bindings)
    hotkey_listener.start()

    # 5. Main thread waits for start signal
    start_signal.wait()

    if script_running:
        do_typing_sequence()

    # 6. Clean up
    print("Script has finished. Exiting.")