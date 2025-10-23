import cv2
import numpy as np
import os
import argparse

# List to store clicked points
points = []

def click_event(event, x, y, flags, param):
    global points, img, original_img

    #  Left click – add points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        cv2.circle(img, (x, y), 5, (0, 0, 255), -1)
        cv2.imshow("Image", img)

        # If two points selected, calculate width & height
        if len(points) == 2:
            (x1, y1), (x2, y2) = points

            width = abs(x2 - x1)
            height = abs(y2 - y1)

            print(f"Width (px): {width}")
            print(f"Height (px): {height}")
            print(f"Diagonal distance (px): {np.sqrt(width**2 + height**2):.2f}")

            # Draw rectangle for visualization
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imshow("Image", img)

    #  Right click – reset everything
    elif event == cv2.EVENT_RBUTTONDOWN:
        print("🔄 Resetting points and image...")
        points.clear()
        img = original_img.copy()
        cv2.imshow("Image", img)

def main():
    parser = argparse.ArgumentParser(description="Calculate dimensions of parking spaces")
    parser.add_argument("-i", "--image", required=True, help="Path to the image file")
    args = parser.parse_args()
    
    base_folder = "data/source/img"
    image_path = os.path.join(base_folder, args.image)
    
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return
    
    global img, original_img
    img = cv2.imread(image_path)
    if img is None:
        print(f"Failed to load image: {image_path}")
        return

    original_img = img.copy()
    
    cv2.imshow("Image", img)
    cv2.setMouseCallback("Image", click_event)

    print(f"\nLoaded image: {image_path}")
    print("Instructions:")
    print("- 🖱️ Left-click two points to measure width/height.")
    print("- 🖱️ Right-click to reset points.")
    print("- ⎋ Press ESC to quit.\n")

    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
