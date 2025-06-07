from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.processor import process_image

router = APIRouter()

class CreateRequest(BaseModel):
    request_id: int

@router.post("/create")
async def create_qr_image(request: CreateRequest):
    try:
        print("이미지 처리시작: %d"%request.request_id)
        result = process_image(request.request_id)
        return {"status": "success", "s3_key": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
