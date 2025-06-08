from pydantic import BaseModel
from typing import List, Optional

class Product(BaseModel):
    product_id: int
    product_name: str

class Coupon(BaseModel):
    coupon_id: int
    registration_code: str
    product: Product

class Issue(BaseModel):
    issue_id: int
    coupons: List[Coupon]
    coupon_image_key: Optional[str] = None

class Partner(BaseModel):
    partner_id: int
    partner_name: str

class Request(BaseModel):
    request_id: int
    partner: Partner
    coupon_form: str

class DataBundle(BaseModel):
    request: Request
    issue: Issue
