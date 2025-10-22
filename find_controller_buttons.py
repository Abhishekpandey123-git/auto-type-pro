import pygame
import time

print("\n--- Game Controller Button/Hat Finder ---")
print("Press any button or D-pad direction on your controller.")
print("Press 'Ctrl+C' to quit when you are done.\n")

# Initialize pygame and the joystick module
pygame.init()
pygame.joystick.init()

# Check if any controllers are connected
joystick_count = pygame.joystick.get_count()
if joystick_count == 0:
    print("Error: No game controller found. Please plug it in and try again.")
    exit()

# Connect to the first controller
controller = pygame.joystick.Joystick(0)
controller.init()
print(f"Successfully connected to controller: {controller.get_name()}")
print("Waiting for input...")

# Loop and listen for events
try:
    while True:
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                print(f"--- Button Pressed: {event.button}")
            
            if event.type == pygame.JOYHATMOTION:
                # event.value will be (x, y)
                # (0, 1) = Up, (0, -1) = Down
                # (1, 0) = Right, (-1, 0) = Left
                print(f"--- D-Pad (Hat) Moved: {event.value}")

        time.sleep(0.01) # Small sleep to not max out the CPU
except KeyboardInterrupt:
    print("\nQuitting button finder. Goodbye!")
    pygame.quit()