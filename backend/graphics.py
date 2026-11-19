"""PNG/HTML generation jobs, independent of screenplay and MP4 queues."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

from .jobs import JobManager, ROOT, now
from .models import GraphicsRequest
from .scripts import ACTIVE, ScriptJobManager, project_script
from render_style import load_render_style


class GraphicsInputError(ValueError):
    pass


def signature(config):
    return json.dumps(config, ensure_ascii=False, separators=(',', ':'))


def completed_snapshot(storage, job, fingerprint):
    """Publish only after every expected phase is present and validated."""
    from generate_kurzge import clean_svg
    from image_motion_ai import Renderer, VERSION
    from plant_kurzge import validate
    output = storage / 'previews' / job['id']
    script = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
    errors = validate(script)
    if errors:
        raise ValueError('; '.join(errors))
    project_script(script)
    context = json.loads((output / 'render_config.json').read_text(encoding='utf-8'))
    verifier = Renderer(script, output, None, clean_svg, style_context=context)
    verifier.library = (output / 'assets.svg').read_text(encoding='utf-8')
    verifier.fingerprint = fingerprint
    playlist_page = (output / 'index.html').read_text(encoding='utf-8')
    match = re.search(r'<script type="application/json" id="data">(.*?)</script>', playlist_page, re.S)
    entries = json.loads(match[1]) if match else []
    expected = [(f'phase_{i}.html', p['name'], p['duration']) for i, p in enumerate(script['phases'], 1)]
    if [(p.get('src'), p.get('title'), p.get('duration')) for p in entries] != expected:
        raise ValueError('Playlist không khớp đầy đủ các phase của kịch bản.')
    rows = []
    for index, phase in enumerate(script['phases'], 1):
        filename = f'phase_{index}.html'
        svg = (output / f'phase_{index}.svg').read_text(encoding='utf-8')
        root = ET.fromstring(svg)
        if root.get('data-fingerprint') != fingerprint or root.get('data-renderer') != VERSION:
            raise ValueError(f'Phase {index} không khớp lần dựng hiện tại.')
        verifier.clean_phase(svg, index)
        page = (output / filename).read_text(encoding='utf-8')
        if svg not in page or 'window.renderAt' not in page:
            raise ValueError(f'Phase {index} thiếu HTML animation hợp lệ.')
        rows.append({'id': str(phase['id']), 'name': phase['name'], 'duration': phase['duration'],
                     'url': f"/api/previews/{job['id']}/{filename}"})
    snapshot = {'id': job['id'], 'revision': fingerprint, 'renderer': VERSION,
                **job['config'], 'sourceSignature': signature(job['config']),
                'duration': sum(p['duration'] for p in script['phases']),
                'width': 1920, 'height': 1080, 'phases': rows}
    temporary = output / 'snapshot.tmp'
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(output / 'snapshot.json')
    return snapshot


class GraphicsJobManager(ScriptJobManager):
    def __init__(self, storage: Path):
        super().__init__(storage, kind='graphics', label='đồ họa')
        self.storage = storage

    def create(self, request: GraphicsRequest):
        config = request.model_dump()
        source = self.storage / 'scripts' / request.scriptId
        try:
            script_job = json.loads((source / 'job.json').read_text(encoding='utf-8'))
            if script_job['status'] != 'succeeded':
                raise GraphicsInputError('Kịch bản chưa tạo thành công. Hãy hoàn tất bước 1.')
            raw = (source / 'kich_ban.json').read_bytes()
            script = json.loads(raw)
            from plant_kurzge import validate_generated
            errors = validate_generated(script)
            if errors:
                raise GraphicsInputError('JSON kịch bản không hợp lệ. Hãy tạo lại ở bước 1.')
            project_script(script)
        except (OSError, json.JSONDecodeError, KeyError) as error:
            raise GraphicsInputError('Không tìm thấy JSON đầy đủ. Hãy tạo lại kịch bản ở bước 1.') from error
        context = load_render_style(request.styleId)
        from image_motion_ai import VERSION
        key = hashlib.sha256(json.dumps({'config': config, 'script': hashlib.sha256(raw).hexdigest(),
                                        'style': context, 'renderer': VERSION},
                                       ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.lock:
            if self.stopping:
                raise RuntimeError('Máy chủ đang dừng.')
            previous = []
            for path in self.root.glob('*/job.json'):
                job = json.loads(path.read_text(encoding='utf-8'))
                if job['projectId'] == request.projectId and job['status'] in ACTIVE:
                    return job
                if job.get('key') == key and job['status'] == 'failed':
                    previous.append(job)
            retry = max(previous, key=lambda j: j['updatedAt']) if previous else None
            job_id = retry['id'] if retry else uuid.uuid4().hex
            directory = self.root / job_id
            # Storage may have been cleaned up since the server started.
            directory.mkdir(parents=True, exist_ok=True)
            output = self.storage / 'previews' / job_id
            output.mkdir(parents=True, exist_ok=True)
            (output / 'kich_ban.json').write_bytes(raw)
            (output / 'render_config.json').write_text(
                json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
            # An incomplete attempt is never served, including after a failed publication.
            (output / 'snapshot.json').unlink(missing_ok=True)
            job = {'id': job_id, 'projectId': request.projectId, 'config': config, 'key': key,
                   'status': 'queued', 'stage': 'queued', 'completed': 0, 'total': 0,
                   'createdAt': retry['createdAt'] if retry else now(), 'updatedAt': now(),
                   'attempt': retry.get('attempt', 1) + 1 if retry else 1,
                   'result': None, 'error': None}
            self.write(job_id, job)
            self.executor.submit(self.run, job_id)
            return job

    def run(self, job_id):
        process = None
        try:
            directory = self.root / job_id
            output = self.storage / 'previews' / job_id
            with (directory / 'worker.log').open('a', encoding='utf-8') as log:
                with self.lock:
                    if self.stopping:
                        return
                    self.update(job_id, status='running', stage='preparing')
                    process = subprocess.Popen(
                        [sys.executable, '-u', '-m', 'backend.graphics_worker', str(output)],
                        cwd=ROOT, stdout=subprocess.PIPE, stderr=log,
                        text=True, encoding='utf-8', start_new_session=True)
                    self.process = process
                outcome = None
                for line in process.stdout:
                    event = json.loads(line)
                    if event.get('stage') in ('preparing', 'images', 'phases', 'checking'):
                        self.update(job_id, stage=event['stage'], completed=event.get('completed', 0),
                                    total=event.get('total', 0))
                    if event.get('status') in ('succeeded', 'failed'):
                        outcome = event
                code = process.wait()
            if not outcome or code != 0:
                raise RuntimeError('Tiến trình dựng đồ họa đã dừng.')
            if outcome['status'] == 'failed':
                self.update(job_id, status='failed', stage='failed', error=outcome['error'])
            else:
                job = self.read(job_id)
                snapshot = completed_snapshot(self.storage, job, outcome['fingerprint'])
                self.update(job_id, status='succeeded', stage='completed', result=snapshot, error=None)
        except Exception:
            self.update(job_id, status='failed', stage='failed', result=None,
                        error='Không thể hoàn tất hoặc lưu toàn bộ animation. Hãy bấm Tạo đồ họa để thử lại.')
        finally:
            if process is not None:
                JobManager.kill_process(process)
                process.wait()
                process.stdout.close()
            with self.lock:
                if self.process is process:
                    self.process = None
