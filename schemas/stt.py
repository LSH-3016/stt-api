from pydantic import BaseModel, Field
from typing import Optional

class STTResponse(BaseModel):
    """STT 변환 응답"""
    text: str = Field(..., description="변환된 텍스트")
    language: str = Field(default="ko-KR", description="감지된 언어")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "안녕하세요, 오늘 날씨가 좋네요",
                "language": "ko-KR"
            }
        }

class STTStreamResponse(BaseModel):
    """STT 스트림 응답"""
    text: str = Field(..., description="변환된 텍스트 (부분)")
    full_text: str = Field(..., description="전체 변환된 텍스트")
    is_final: bool = Field(default=False, description="최종 결과 여부")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "오늘 아침",
                "full_text": "오늘 아침 7시에 기상했다",
                "is_final": False
            }
        }
