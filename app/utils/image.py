import cv2
import numpy as np
import pytesseract
from typing import Tuple, Optional

def detect_placeholder_region(image: np.ndarray, placeholder: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect the bounding box of a specific placeholder text in the image using OCR.

    Args:
        image (np.ndarray): The image to search.
        placeholder (str): The placeholder text to find.

    Returns:
        Optional[Tuple[int, int, int, int]]: Bounding box (x, y, w, h) if found, else None.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

    for i, text in enumerate(data["text"]):
        if text.strip() == placeholder:
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            return x, y, w, h
    return None

def detect_red_rectangle(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect the largest red rectangle in the image.

    Args:
        image (np.ndarray): Input BGR image.

    Returns:
        Optional[Tuple[int, int, int, int]]: Bounding box (x, y, w, h) of red region.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([179, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        return x, y, w, h
    return None
