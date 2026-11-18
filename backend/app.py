from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .jobs import JobManager, ROOT
from .models import ExportRequest, PreviewRequest
from .previews import create_preview


def create_app(storage_root: Path | None = None):
    storage = (storage_root or Path(os.environ.get('VIDEO_STORAGE_DIR', ROOT / 'storage'))).resolve()

    @asynccontextmanager
    async def lifespan(app):
        app.state.jobs = JobManager(storage)
        yield
        app.state.jobs.close()

    app = FastAPI(title='AI Video Studio', lifespan=lifespan)

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

    @app.post('/api/previews', status_code=201)
    def preview(request: PreviewRequest):
        snapshot_id = uuid.uuid4().hex
        return create_preview(request, storage / 'previews' / snapshot_id, snapshot_id)

    @app.get('/api/previews/{snapshot_id}')
    def get_preview(snapshot_id: str):
        return json.loads((snapshot_path(snapshot_id) / 'snapshot.json').read_text())

    @app.get('/api/previews/{snapshot_id}/{filename}')
    def phase(snapshot_id: str, filename: str):
        path = snapshot_path(snapshot_id)
        if not re.fullmatch(r'phase_[1-9][0-9]*\.html', filename) or not (path / filename).is_file():
            raise HTTPException(404, 'Không tìm thấy phase.')
        return FileResponse(path / filename, media_type='text/html', headers={'Cache-Control': 'no-store'})

    @app.post('/api/exports', status_code=202)
    def export(request: ExportRequest):
        try:
            return app.state.jobs.create(request)
        except FileNotFoundError:
            raise HTTPException(404, 'Preview không còn trên máy chủ. Hãy tạo lại animation.')

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
