import os
import cv2
import boto3
import numpy as np
from io import BytesIO
from PIL import Image
from app.utils.image import detect_placeholder_region, detect_red_rectangle
from app.utils.qrcode import generate_qr_image
from app.models.schema import DataBundle
from app.services.data_loader import load_data_by_request_id
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

def process_image(request_id: int) -> str:
    # 데이터 로드
    data: DataBundle = load_data_by_request_id(request_id)
    try:
        base_key = data.request.coupon_form
        print("템플릿 이미지 key: %s" % base_key)

        # S3에서 원본 이미지 다운로드
        response = s3.get_object(Bucket=BUCKET_NAME, Key=base_key)
        image_data = np.asarray(bytearray(response["Body"].read()), dtype=np.uint8)
        template_img = cv2.imdecode(image_data, cv2.IMREAD_COLOR)

        processed_images = []

        for coupon in data.issue.coupons:
            # 이미지 복사
            img = template_img.copy()

            # 텍스트 치환
            menu_box = detect_placeholder_region(img, "{{MENU_NAME}}")
            if menu_box:
                x, y, w, h = menu_box
                cv2.rectangle(img, (x, y), (x+w, y+h), (255, 255, 255), -1)
                img = draw_text_with_font(img, coupon.product.product_name, (x, y), font_size=32)

            partner_box = detect_placeholder_region(img, "{{PARTNER_NAME}}")
            if partner_box:
                x, y, w, h = partner_box
                cv2.rectangle(img, (x, y), (x+w, y+h), (255, 255, 255), -1)
                img = draw_text_with_font(img, data.request.partner.partner_name, (x, y), font_size=32)

            # QR 코드 삽입
            red_box = detect_red_rectangle(img)
            if red_box:
                x, y, w, h = red_box
                qr_img = generate_qr_image(coupon.registration_code, size=w)
                qr_img = cv2.resize(qr_img, (w, h))
                img[y:y+h, x:x+w] = qr_img

            processed_images.append(img)

        # A4 크기 설정 (단위: 픽셀)
        a4_width, a4_height = 2480, 3508  # A4 at 300 DPI
        thumb_w, thumb_h = processed_images[0].shape[1], processed_images[0].shape[0]
        cols = a4_width // thumb_w
        rows_per_page = a4_height // thumb_h
        images_per_page = cols * rows_per_page
        total_pages = math.ceil(len(processed_images) / images_per_page)

        s3_keys = []

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
                cv2.rectangle(canvas, (x, y), (x + thumb_w - 1, y + thumb_h - 1), (0, 0, 0), 2)  # Black border

            output_filename = f"{request_id}_sheet_{page_num + 1}.png"
            local_path = os.path.join(TEMP_DIR, output_filename)
            cv2.imwrite(local_path, canvas)

            s3_key = f"result/{output_filename}"
            with open(local_path, "rb") as f:
                s3.upload_fileobj(f, BUCKET_NAME, s3_key)

            s3_keys.append(s3_key)

        print(f"Uploaded {len(s3_keys)} A4 sheet image(s) to S3: {s3_keys}")
        return s3_keys
    except Exception as e:
        print(f"[ERROR] Failed to process image for request_id={request_id}: {e}")
        raise
