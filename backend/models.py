from typing import Annotated, Literal
import math
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator

STYLE_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'skills' / 'style_config.json'
ConfigStyleId = Annotated[str, Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')]
LEGACY_STYLE_IDS = {'detailed-vector', 'outlined-cartoon', 'cartoon', 'dark', 'watercolor', 'pixel', 'sketch', 'flat'}


class StyleCategory(BaseModel):
    label: str = Field(min_length=1)
    allowed_styles: list[ConfigStyleId] = Field(min_length=1)


class StyleConfiguration(BaseModel):
    categories: dict[str, StyleCategory] = Field(min_length=1)
    default_style: ConfigStyleId


def load_style_config():
    return StyleConfiguration.model_validate_json(
        STYLE_CONFIG_PATH.read_text(encoding='utf-8')
    ).model_dump()


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


class ScriptRequest(BaseModel):
    projectId: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=5 * 1024 * 1024)

    @field_validator('content')
    @classmethod
    def nonblank_content(cls, value):
        if not value.strip():
            raise ValueError('Nội dung đầu vào trống.')
        return value


class PreviewRequest(BaseModel):
    projectId: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=160)
    categoryId: str | None = None
    styleId: ConfigStyleId
    scenes: list[Scene] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def valid_timeline(self):
        try:
            config = load_style_config()
        except (OSError, ValueError):
            raise ValueError('Không đọc được cấu hình danh mục. Hãy kiểm tra skills/style_config.json.')
        if self.categoryId is not None:
            category = config['categories'].get(self.categoryId)
            if category is None:
                raise ValueError('Danh mục kịch bản không hợp lệ.')
            if self.styleId not in category['allowed_styles']:
                raise ValueError(f"Phong cách không được phép cho danh mục {category['label']}.")
        elif self.styleId not in LEGACY_STYLE_IDS and not any(
            self.styleId in category['allowed_styles'] for category in config['categories'].values()
        ):
            raise ValueError('Phong cách không tồn tại trong cấu hình.')
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
