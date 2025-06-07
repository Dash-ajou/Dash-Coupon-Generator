import qrcode
import numpy as np
import cv2
from io import BytesIO

def generate_qr_image(data: str, size: int = 200) -> np.ndarray:
    """
    Generate a QR code image from the given data string.

    Args:
        data (str): The data to encode in the QR code.
        size (int): The desired width and height of the QR code image.

    Returns:
        np.ndarray: The QR code image as a BGR OpenCV image.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img_pil = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img_bytes = BytesIO()
    img_pil.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    file_bytes = np.asarray(bytearray(img_bytes.read()), dtype=np.uint8)
    img_cv = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if size:
        img_cv = cv2.resize(img_cv, (size, size), interpolation=cv2.INTER_AREA)

    return img_cv
