from datetime import datetime
import os
import cv2
import boto3
import numpy as np
from io import BytesIO
from PIL import Image
from app.utils.image import detect_placeholder_region, detect_red_rectangle
from app.utils.qrcode import generate_qr_image
from app.models.schema import DataBundle
from app.services.data_loader import load_data_by_request_id, update_coupon_image_key
from dotenv import load_dotenv
import math
from PIL import ImageFont, ImageDraw, Image

load_dotenv()
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION")
)
BUCKET_NAME = os.getenv("S3_BUCKET")
TEMP_DIR = "/tmp"

def draw_text_with_font(img_cv, text, position, font_path="font/NSKR.ttf", font_size=32):
    img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = ImageFont.truetype(font_path, font_size)
    draw.text(position, text, font=font, fill=(0, 0, 0))  # Black text
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


# Helper: 템플릿 이미지 조회
def load_template_image(base_key: str) -> np.ndarray:
    response = s3.get_object(Bucket=BUCKET_NAME, Key=base_key)
    image_data = np.asarray(bytearray(response["Body"].read()), dtype=np.uint8)
    return cv2.imdecode(image_data, cv2.IMREAD_COLOR)

# Helper: 쿠폰이미지 합성
def process_coupon(template_img, coupon, partner_name):
    img = template_img.copy()

    menu_box = detect_placeholder_region(img, "{{MENU_NAME}}")
    if menu_box:
        x, y, w, h = menu_box
        cv2.rectangle(img, (x, y), (x+w, y+h), (255, 255, 255), -1)
        img = draw_text_with_font(img, coupon.product.product_name, (x, y), font_size=32)

    partner_box = detect_placeholder_region(img, "{{PARTNER_NAME}}")
    if partner_box:
        x, y, w, h = partner_box
        cv2.rectangle(img, (x, y), (x+w, y+h), (255, 255, 255), -1)
        img = draw_text_with_font(img, partner_name, (x, y), font_size=32)

    rc_box = detect_placeholder_region(img, "{{REGISTRATION_CODE}}")
    if rc_box:
        x, y, w, h = rc_box
        cv2.rectangle(img, (x, y), (x+w, y+h), (255, 255, 255), -1)
        img = draw_text_with_font(img, coupon.registration_code, (x, y), font_size=24)

    red_box = detect_red_rectangle(img)
    if red_box:
        x, y, w, h = red_box
        qr_img = generate_qr_image(coupon.registration_code, size=w)
        qr_img = cv2.resize(qr_img, (w, h))
        img[y:y+h, x:x+w] = qr_img
    return img

# Helper: A4이미지 내에 쿠폰이미지 병합
def compose_to_pages(processed_images):
    a4_width, a4_height = 2480, 3508
    thumb_w, thumb_h = processed_images[0].shape[1], processed_images[0].shape[0]
    cols = a4_width // thumb_w
    rows_per_page = a4_height // thumb_h
    images_per_page = cols * rows_per_page
    total_pages = math.ceil(len(processed_images) / images_per_page)
    pages = []

    for page_num in range(total_pages):
        canvas = np.ones((a4_height, a4_width, 3), dtype=np.uint8) * 255
        for idx in range(images_per_page):
            global_idx = page_num * images_per_page + idx
            if global_idx >= len(processed_images):
                break
            img = processed_images[global_idx]
            local_idx = idx
            row = local_idx // cols
            col = local_idx % cols
            y, x = row * thumb_h, col * thumb_w
            canvas[y:y+thumb_h, x:x+thumb_w] = img
            cv2.rectangle(canvas, (x, y), (x + thumb_w - 1, y + thumb_h - 1), (0, 0, 0), 2)
        pages.append(canvas)
    return pages

def compose_to_backpages(processed_images):
    a4_width, a4_height = 2480, 3508
    thumb_w, thumb_h = processed_images[0].shape[1], processed_images[0].shape[0]
    cols = a4_width // thumb_w
    rows_per_page = a4_height // thumb_h
    images_per_page = cols * rows_per_page
    total_pages = math.ceil(len(processed_images) / images_per_page)
    pages = []

    for page_num in range(total_pages):
        canvas = np.ones((a4_height, a4_width, 3), dtype=np.uint8) * 255
        for idx in range(images_per_page):
            global_idx = page_num * images_per_page + idx
            if global_idx >= len(processed_images):
                break
            img = processed_images[global_idx]
            local_idx = idx
            row = local_idx // cols
            col = local_idx % cols
            # X 좌표를 우측 정렬 방식으로 계산
            x = a4_width - (cols - col) * thumb_w
            y = row * thumb_h
            canvas[y:y+thumb_h, x:x+thumb_w] = img
            cv2.rectangle(canvas, (x, y), (x + thumb_w - 1, y + thumb_h - 1), (0, 0, 0), 2)
        pages.append(canvas)
    return pages

# Helper: S3 업로드
def upload_pages_to_s3(coupon_images, request_id):
    pdf_filename = f"{int(datetime.now().timestamp() * 1000)}_coupon_image.pdf"
    pdf_path = os.path.join(TEMP_DIR, pdf_filename)

    # Load back template image from S3
    back_template_key = "static/back_template.png"
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=back_template_key)
        back_img_data = response["Body"].read()
        back_img_cv = cv2.imdecode(np.frombuffer(back_img_data, np.uint8), cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"[ERROR] Failed to load back template from S3: {e}")
        raise

    # Compose front pages
    front_pages = compose_to_pages(coupon_images)

    # Create matching number of back images
    back_images = [back_img_cv] * len(coupon_images)

    # Compose back pages
    back_pages = compose_to_backpages(back_images)

    # Interleave front and back pages
    pil_pages = []
    for front, back in zip(front_pages, back_pages):
        pil_pages.append(Image.fromarray(cv2.cvtColor(front, cv2.COLOR_BGR2RGB)).convert("RGB"))
        pil_pages.append(Image.fromarray(cv2.cvtColor(back, cv2.COLOR_BGR2RGB)).convert("RGB"))

    if pil_pages:
        pil_pages[0].save(pdf_path, save_all=True, append_images=pil_pages[1:])

        s3_key = f"image/{pdf_filename}"
        with open(pdf_path, "rb") as f:
            s3.upload_fileobj(f, BUCKET_NAME, s3_key)
            update_coupon_image_key(request_id, s3_key)
        return [s3_key]
    return []

# 처리로직
def process_image(request_id: int) -> str:
    data: DataBundle = load_data_by_request_id(request_id)
    try:
        base_key = data.request.coupon_form
        print("ㄴ 템플릿 이미지 key: %s" % base_key)
        template_img = load_template_image(base_key)
        processed_images = [process_coupon(template_img, c, data.request.partner.partner_name) for c in data.issue.coupons]
        pages = compose_to_pages(processed_images)
        s3_keys = upload_pages_to_s3(processed_images, request_id)
        print(f"ㄴ Uploaded {len(s3_keys)} A4 sheet image(s) to S3: {s3_keys}")
        return s3_keys
    except Exception as e:
        print(f"ㄴ [ERROR] Failed to process image for request_id={request_id}: {e}")
        raise
