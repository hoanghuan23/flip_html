from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ExportConfig(BaseModel):
    filename: str = Field(default='video-cua-toi', min_length=1, max_length=120, validate_default=True)
    fps: Literal[24, 30, 60] = 30
    quality: Literal['draft', 'looks', 'delivery'] = 'delivery'

    @field_validator('filename')
    @classmethod
    def safe_filename(cls, value):
        value = value.strip()
        if not value or any(c in value for c in '/\\\x00\r\n') or value in ('.', '..'):
            raise ValueError('Tên file không hợp lệ.')
        return value if value.lower().endswith('.mp4') else value + '.mp4'


class ExportRequest(BaseModel):
    snapshotId: str = Field(pattern=r'^[a-f0-9]{32}$')
    config: ExportConfig
