import cv2
import numpy as np
import os

# List to store clicked points
points = []

def click_event(event, x, y, flags, param):
    global points, img

    # When left mouse button is clicked
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

# Load your image
img = cv2.imread("data/source/blok2_image.png")
cv2.imshow("Image", img)

cv2.setMouseCallback("Image", click_event)

cv2.waitKey(0)
cv2.destroyAllWindows()
