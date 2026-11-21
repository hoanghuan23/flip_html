"""Persistent screenplay jobs; AI runs in a separate, stoppable process."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import threading
import uuid

from pydantic import ValidationError

from .jobs import ROOT, JobManager, now
from .models import Scene, ScriptRequest

ACTIVE = ('queued', 'running')


def project_script(script):
    """Validate UI compatibility, then extract without altering the AI source."""
    title = script.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise ValueError('Tiêu đề kịch bản phải có nội dung và tối đa 160 ký tự.')
    phases = script['phases']
    if not 1 <= len(phases) <= 100:
        raise ValueError('Giao diện hỗ trợ từ 1 đến 100 cảnh.')
    scenes = []
    for phase in phases:
        scene = {'id': str(phase['id']), 'name': phase.get('name'),
                 'narration': phase.get('narration'), 'description': phase.get('description'),
                 'duration': phase['duration']}
        if 'voiceover' in phase:
            scene['voiceover'] = phase['voiceover']
        for field in ('annotations', 'duration_status'):
            if field in phase:
                scene[field] = phase[field]
        try:
            Scene.model_validate(scene)
        except ValidationError as error:
            details = '; '.join(f"{e['loc'][0]}: {e['msg']}" for e in error.errors())
            raise ValueError(f"Phase {phase['id']} không phù hợp giao diện: {details}") from error
        scenes.append(scene)
    if sum(scene['duration'] for scene in scenes) > 1800:
        raise ValueError('Giao diện hỗ trợ tổng thời lượng tối đa 30 phút.')
    result = {'title': title, 'scenes': scenes}
    for field in ('input_type', 'research', 'warnings'):
        if field in script:
            result[field] = script[field]
    return result


def validate_for_ui(script):
    try:
        project_script(script)
        return []
    except ValueError as error:
        return [str(error)]


class ScriptJobManager:
    def __init__(self, storage: Path, *, kind='scripts', label='kịch bản'):
        self.root = storage / kind
        self.label = label
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=kind)
        self.process = None
        self.stopping = False
        for path in self.root.glob('*/job.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            if data['status'] in ACTIVE:
                self.update(data['id'], status='failed', stage='failed',
                            error=f'Máy chủ đã khởi động lại. Hãy tạo lại {self.label}.')

    def read(self, job_id):
        with self.lock:
            return json.loads((self.root / job_id / 'job.json').read_text(encoding='utf-8'))

    def write(self, job_id, data):
        path = self.root / job_id / 'job.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)

    def update(self, job_id, **changes):
        with self.lock:
            data = self.read(job_id)
            data.update(changes, updatedAt=now())
            self.write(job_id, data)
            return data

    def create(self, request: ScriptRequest):
        with self.lock:
            if self.stopping:
                raise RuntimeError('Máy chủ đang dừng. Hãy thử lại.')
            for path in self.root.glob('*/job.json'):
                job = json.loads(path.read_text(encoding='utf-8'))
                if job['projectId'] == request.projectId and job['status'] in ACTIVE:
                    return job
            job_id = uuid.uuid4().hex
            directory = self.root / job_id
            directory.mkdir()
            (directory / 'input.txt').write_text(request.content, encoding='utf-8')
            job = {'id': job_id, 'projectId': request.projectId, 'status': 'queued',
                   'stage': 'queued', 'createdAt': now(), 'updatedAt': now(),
                   'error': None, 'result': None}
            self.write(job_id, job)
            self.executor.submit(self.run, job_id)
            return job

    def run(self, job_id):
        process = None
        try:
            with self.lock:
                if self.stopping:
                    return
                self.update(job_id, status='running', stage='validating')
                process = subprocess.Popen(
                    [sys.executable, '-u', '-m', 'backend.script_worker', str(self.root / job_id)],
                    cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding='utf-8', start_new_session=True,
                )
                self.process = process
            outcome = None
            for line in process.stdout:
                event = json.loads(line)
                if event.get('stage') in ('validating', 'classifying', 'researching', 'generating', 'normalizing', 'saving'):
                    self.update(job_id, stage=event['stage'])
                if event.get('status') in ('succeeded', 'rejected', 'failed'):
                    outcome = event
            code = process.wait()
            if outcome is None or (code != 0 and outcome['status'] == 'succeeded'):
                raise RuntimeError('Tiến trình AI đã dừng. Hãy tạo lại kịch bản.')
            if outcome['status'] == 'succeeded':
                # Success is published only after the canonical JSON exists and passes checks.
                from plant_kurzge import validate_generated
                script = json.loads((self.root / job_id / 'kich_ban.json').read_text(encoding='utf-8'))
                errors = validate_generated(script)
                if errors:
                    raise ValueError('\n'.join(errors))
                self.update(job_id, status='succeeded', stage='completed',
                            result=project_script(script), error=None)
            else:
                self.update(job_id, status=outcome['status'], stage=outcome['status'],
                            error=outcome['error'], result=None)
        except Exception:
            self.update(job_id, status='failed', stage='failed', result=None,
                        error='Không thể hoàn tất hoặc lưu kịch bản. Hãy kiểm tra máy chủ và thử lại.')
        finally:
            if process is not None:
                JobManager.kill_process(process)
                process.wait()
                if process.stdout:
                    process.stdout.close()
            with self.lock:
                if self.process is process:
                    self.process = None

    def close(self):
        with self.lock:
            self.stopping = True
            JobManager.kill_process(self.process)
        self.executor.shutdown(wait=True, cancel_futures=True)
        for path in self.root.glob('*/job.json'):
            job = json.loads(path.read_text(encoding='utf-8'))
            if job['status'] in ACTIVE:
                self.update(job['id'], status='failed', stage='failed',
                            error=f'Máy chủ đã dừng. Hãy tạo lại {self.label}.')
