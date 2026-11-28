from typing import Literal
import math
from pydantic import BaseModel, Field, field_validator
from .image_store import ImageBinding


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


class Annotation(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1)
    action_index: int | None = Field(default=None, ge=0, strict=True)
    cue: str | None = Field(default=None, min_length=1)


class Scene(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    narration: str = Field(max_length=2000)
    description: str = Field(max_length=3000)
    duration: float = Field(gt=0, le=120)
    voiceover: str | None = Field(default=None, max_length=10000)
    annotations: list[Annotation] | None = None
    duration_status: Literal['estimated'] | None = None

    @field_validator('duration')
    @classmethod
    def finite_duration(cls, value):
        if not math.isfinite(value):
            raise ValueError('Thời lượng phải là số hữu hạn.')
        return value

    @field_validator('name')
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError('Tên cảnh không được để trống.')
        return value.strip()


class ScriptRequest(BaseModel):
    projectId: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    content: str = Field(min_length=1, max_length=5 * 1024 * 1024)
    images: list[ImageBinding] = Field(default_factory=list, max_length=100)

    @field_validator('content')
    @classmethod
    def nonblank_content(cls, value):
        if not value.strip():
            raise ValueError('Nội dung đầu vào trống.')
        return value
