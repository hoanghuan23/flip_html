from typing import Literal
import math
from pydantic import BaseModel, Field, field_validator, model_validator

StyleId = Literal['cartoon', 'dark', 'watercolor', 'pixel', 'sketch', 'flat']


class Scene(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    narration: str = Field(max_length=2000)
    description: str = Field(max_length=3000)
    duration: float = Field(gt=0, le=120)

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


class PreviewRequest(BaseModel):
    projectId: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=160)
    styleId: StyleId
    scenes: list[Scene] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def valid_timeline(self):
        if len({scene.id for scene in self.scenes}) != len(self.scenes):
            raise ValueError('ID cảnh phải khác nhau.')
        if sum(s.duration for s in self.scenes) > 1800:
            raise ValueError('Bản đầu hỗ trợ video tối đa 30 phút.')
        return self


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
