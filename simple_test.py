import pyautogui
import time

print("--- Starting Simple Test in 5 seconds ---")
print("Click on an empty Notepad or VS Code window NOW.")

# Give yourself time to switch windows
time.sleep(5)

print("Now attempting to control mouse and keyboard...")

try:
    # Test 1: Move the mouse to a specific location
    pyautogui.moveTo(300, 300, duration=1)
    print("SUCCESS: Mouse moved to (300, 300).")

    # Test 2: Type a simple string
    pyautogui.write("Hello World! PyAutoGUI is working.", interval=0.1)
    print("SUCCESS: Typed 'Hello World!'.")

    print("\n--- Test Complete ---")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")