from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
import shutil

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .jobs import JobManager, PreviewNotFoundError, ROOT
from .models import ExportRequest
from .image_store import ImageUpload, save_image
from .character_ai import router as character_ai_router


def create_app(storage_root: Path | None = None):
    storage = (storage_root or Path(os.environ.get('VIDEO_STORAGE_DIR', ROOT / 'storage'))).resolve()

    @asynccontextmanager
    async def lifespan(app):
        app.state.jobs = JobManager(storage)
        try:
            yield
        finally:
            app.state.jobs.close()

    app = FastAPI(title='AI Video Studio', lifespan=lifespan)
    app.state.storage_root = storage
    app.include_router(character_ai_router)

    def checked_id(value):
        if not re.fullmatch(r'[a-f0-9]{32}', value):
            raise HTTPException(404, 'Không tìm thấy dữ liệu.')
        return value

    def snapshot_path(snapshot_id):
        path = storage / 'previews' / checked_id(snapshot_id)
        if not (path / 'snapshot.json').is_file():
            raise HTTPException(404, 'Preview không còn trên máy chủ. Hãy tạo lại animation.')
        return path

    def read_job(job_id):
        checked_id(job_id)
        try:
            return app.state.jobs.read(job_id)
        except FileNotFoundError:
            raise HTTPException(404, 'Không tìm thấy tác vụ xuất video.')

    @app.get('/api/health')
    def health():
        dependencies = {name: bool(shutil.which(name)) for name in ('node', 'npx', 'ffmpeg', 'ffprobe')}
        dependencies['chrome'] = bool(os.environ.get('PUPPETEER_EXECUTABLE_PATH') or
                                      any(shutil.which(p) for p in ('google-chrome', 'chromium', 'chromium-browser')))
        return {'ready': all(dependencies.values()), 'dependencies': dependencies}

    @app.post('/api/previews')
    @app.post('/api/scripts')
    @app.post('/api/graphics')
    @app.post('/api/graphics/{graphics_id}/confirm')
    def generation_unavailable():
        raise HTTPException(503, 'Chưa có cấu hình tạo nội dung.')

    @app.post('/api/images', status_code=201)
    def upload_image(request: ImageUpload):
        try:
            return save_image(storage, request)
        except ValueError as error:
            raise HTTPException(422, str(error))
        except OSError:
            raise HTTPException(503, 'Không thể lưu ảnh trên máy chủ.')

    @app.get('/api/previews/{snapshot_id}')
    def get_preview(snapshot_id: str):
        return json.loads((snapshot_path(snapshot_id) / 'snapshot.json').read_text())

    @app.get('/api/previews/{snapshot_id}/index.html')
    def preview_playlist(snapshot_id: str):
        path = snapshot_path(snapshot_id) / 'index.html'
        if not path.is_file():
            raise HTTPException(404, 'Không tìm thấy trình phát preview.')
        return FileResponse(path, media_type='text/html', headers={'Cache-Control': 'no-store'})

    @app.get('/api/previews/{snapshot_id}/{filename}')
    def phase(snapshot_id: str, filename: str):
        path = snapshot_path(snapshot_id)
        if not re.fullmatch(r'phase_[1-9][0-9]*\.html', filename) or not (path / filename).is_file():
            raise HTTPException(404, 'Không tìm thấy phase.')
        return FileResponse(path / filename, media_type='text/html', headers={'Cache-Control': 'no-store'})

    @app.get('/api/previews/{snapshot_id}/assets/{asset_path:path}')
    def preview_asset(snapshot_id: str, asset_path: str):
        root = snapshot_path(snapshot_id) / 'assets'
        path = (root / asset_path).resolve()
        if (not path.is_relative_to(root.resolve()) or not path.is_file()
                or path.suffix.lower() not in {'.js', '.css', '.woff', '.woff2', '.ttf', '.otf', '.mp3', '.wav', '.png', '.jpeg', '.jpg', '.webp', '.svg'}):
            raise HTTPException(404, 'Không tìm thấy tài nguyên preview.')
        return FileResponse(path, headers={'Cache-Control': 'public, max-age=31536000, immutable'})

    @app.post('/api/exports', status_code=202)
    def export(request: ExportRequest):
        try:
            return app.state.jobs.create(request)
        except PreviewNotFoundError:
            raise HTTPException(404, 'Preview không còn trên máy chủ. Hãy tạo lại animation.')
        except (OSError, RuntimeError):
            raise HTTPException(503, 'Không thể tạo hoặc lưu tác vụ xuất video. Hãy kiểm tra thư mục lưu trữ trên máy chủ và thử lại.')

    @app.get('/api/exports/{job_id}')
    def job(job_id: str):
        return read_job(job_id)

    def video_response(job_id, download):
        job = read_job(job_id)
        if job['status'] != 'succeeded':
            raise HTTPException(409, 'Video chưa xuất xong.')
        path = storage / 'exports' / job_id / 'video.mp4'
        if not path.is_file():
            raise HTTPException(404, 'File video không còn trên máy chủ. Hãy xuất lại.')
        return FileResponse(path, media_type='video/mp4', filename=job['config']['filename'],
                            content_disposition_type='attachment' if download else 'inline')

    @app.get('/api/exports/{job_id}/video')
    def video(job_id: str):
        return video_response(job_id, False)

    @app.get('/api/exports/{job_id}/download')
    def download(job_id: str):
        return video_response(job_id, True)

    # API routes precede static files, so missing API paths never return index.html.
    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def missing_api(path: str):
        raise HTTPException(404, 'API không tồn tại.')

    dist = ROOT / 'frontend' / 'dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    else:
        @app.get('/')
        def setup():
            return {'message': 'Chạy npm install && npm run build trong frontend/, hoặc dùng Vite ở cổng 5173.'}
    return app


app = create_app()
