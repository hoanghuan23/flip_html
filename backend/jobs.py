"""One render worker, persistent metadata, and restart recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid

from .models import ExportRequest

ROOT = Path(__file__).resolve().parent.parent


def now():
    return datetime.now(timezone.utc).isoformat()


class PreviewNotFoundError(FileNotFoundError):
    """The requested snapshot is missing, independently of export storage."""


class JobManager:
    def __init__(self, storage: Path):
        self.storage = storage
        self.jobs = storage / 'exports'
        self.jobs.mkdir(parents=True, exist_ok=True)
        (storage / 'previews').mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='render')
        self.process = None
        self.stopping = False
        for path in self.jobs.glob('*/job.json'):
            data = json.loads(path.read_text())
            if data['status'] in ('queued', 'running'):
                self.update(data['id'], status='failed', stage='failed',
                            error='Máy chủ đã khởi động lại. Hãy thử xuất lại video.')

    def read(self, job_id):
        with self.lock:
            path = self.jobs / job_id / 'job.json'
            if not path.is_file():
                raise FileNotFoundError(job_id)
            return json.loads(path.read_text(encoding='utf-8'))

    def update(self, job_id, **changes):
        with self.lock:
            data = self.read(job_id)
            data.update(changes, updatedAt=now())
            self.write(job_id, data)
            return data

    def write(self, job_id, data):
        path = self.jobs / job_id / 'job.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)

    def create(self, request: ExportRequest):
        with self.lock:
            snapshot_root = self.storage / 'previews' / request.snapshotId
            try:
                snapshot = json.loads((snapshot_root / 'snapshot.json').read_text())
            except FileNotFoundError as error:
                raise PreviewNotFoundError(request.snapshotId) from error
            config = request.config.model_dump()
            for path in self.jobs.glob('*/job.json'):
                job = json.loads(path.read_text())
                if (job['status'] in ('queued', 'running') and
                        job['snapshotId'] == request.snapshotId and job['config'] == config):
                    return job
            job_id = uuid.uuid4().hex
            directory = self.jobs / job_id
            # Export storage may have been cleaned up since the server started.
            directory.mkdir(parents=True)
            job = {'id': job_id, 'snapshotId': request.snapshotId,
                   'revision': snapshot['revision'], 'status': 'queued', 'stage': 'queued',
                   'createdAt': now(), 'updatedAt': now(), 'config': config,
                   'duration': snapshot['duration'], 'width': snapshot['width'],
                   'height': snapshot['height'], 'error': None, 'result': None, 'progress': None}
            self.write(job_id, job)
            self.executor.submit(self.render, job_id)
            return job

    def render(self, job_id):
        process = None
        try:
            with self.lock:
                if self.stopping:
                    return
            job = self.update(job_id, status='running', stage='preparing', startedAt=now())
            directory = self.jobs / job_id
            output = directory / 'video.mp4'
            command = [sys.executable, '-u', str(ROOT / 'render_hyperframes.py'),
                       '--input', str(self.storage / 'previews' / job['snapshotId']),
                       '--output', str(output), '--fps', str(job['config']['fps']),
                       '--quality', job['config']['quality']]
            if os.environ.get('HYPERFRAMES_COMMAND'):
                command.extend(['--hyperframes-command', os.environ['HYPERFRAMES_COMMAND']])
            with (directory / 'render.log').open('w', encoding='utf-8') as log:
                with self.lock:
                    if self.stopping:
                        raise RuntimeError('Máy chủ đang dừng. Hãy thử xuất lại.')
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                               text=True, bufsize=1, cwd=ROOT, start_new_session=True)
                    self.process = process
                # A timer terminates the entire CLI/Chrome process group, not only Python.
                timed_out = threading.Event()

                def timeout():
                    timed_out.set()
                    self.kill_process(process)

                timer = threading.Timer(3600, timeout)
                timer.start()
                recent = []
                rendering = False
                try:
                    for line in process.stdout:
                        log.write(line)
                        log.flush()
                        recent.append(line.strip())
                        recent = recent[-12:]
                        if line.startswith('+ ') and ' check ' in line:
                            self.update(job_id, stage='checking')
                        elif line.startswith('+ ') and ' snapshot ' in line:
                            self.update(job_id, stage='snapshotting')
                        elif line.startswith('+ ') and ' render ' in line:
                            rendering = True
                            self.update(job_id, stage='rendering')
                        elif line.startswith('Xác minh MP4'):
                            self.update(job_id, stage='verifying')
                        elif rendering and line.startswith('@hf-progress '):
                            try:
                                pct = json.loads(line[len('@hf-progress '):]).get('pct')
                                if isinstance(pct, (int, float)) and 0 <= pct <= 100:
                                    self.update(job_id, progress=min(99, pct))
                            except (ValueError, TypeError):
                                pass
                    code = process.wait()
                finally:
                    timer.cancel()
                if timed_out.is_set():
                    raise RuntimeError('Xuất video vượt quá 60 phút. Hãy giảm FPS hoặc chất lượng và thử lại.')
                if code:
                    detail = next((line.removeprefix('Lỗi: ') for line in reversed(recent)
                                   if line.startswith('Lỗi:')), 'Không thể hoàn tất render. Xem render.log trên máy chủ.')
                    # Do not expose local directory names in user-facing messages.
                    detail = detail.replace(str(ROOT), '[dự án]').replace(str(self.storage), '[lưu trữ]')
                    raise RuntimeError(detail)
            size = output.stat().st_size
            if size == 0:
                raise RuntimeError('Video xuất ra rỗng. Hãy thử lại.')
            self.update(job_id, status='succeeded', stage='complete', completedAt=now(), progress=100,
                        result={'videoUrl': f'/api/exports/{job_id}/video',
                                'downloadUrl': f'/api/exports/{job_id}/download', 'bytes': size})
        except Exception as exc:
            self.update(job_id, status='failed', stage='failed', error=str(exc), completedAt=now())
        finally:
            if process is not None and process.poll() is None:
                self.kill_process(process)
                process.wait()
            with self.lock:
                if self.process is process:
                    self.process = None

    @staticmethod
    def kill_process(process):
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self):
        with self.lock:
            self.stopping = True
            self.kill_process(self.process)
        self.executor.shutdown(wait=True, cancel_futures=True)
        for path in self.jobs.glob('*/job.json'):
            job = json.loads(path.read_text())
            if job['status'] in ('queued', 'running'):
                self.update(job['id'], status='failed', stage='failed',
                            error='Máy chủ đã dừng. Hãy thử xuất lại video.')
