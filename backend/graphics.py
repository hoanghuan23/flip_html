"""PNG/HTML generation jobs, independent of screenplay and MP4 queues."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import traceback
import uuid
import shutil
import xml.etree.ElementTree as ET

from .jobs import JobManager, ROOT, now
from .models import GraphicsRequest
from .scripts import ACTIVE, ScriptJobManager, project_script
from render_style import load_render_context
from .still_previews import load_stills


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
    from .narration import probe_audio
    for phase, row in zip(script['phases'], rows):
        if phase.get('voiceover') and not phase.get('audio'):
            raise ValueError('Thiếu audio cho cảnh có lời thuyết minh.')
        if phase.get('audio'):
            audio = phase['audio']
            path = (output / audio['src']).resolve()
            if not path.is_relative_to((output / 'assets/audio').resolve()):
                raise ValueError('Đường dẫn audio không hợp lệ.')
            actual = probe_audio(path)
            if abs(actual - audio['duration']) > .01 or hashlib.sha256(path.read_bytes()).hexdigest() != audio['sha256']:
                raise ValueError('Audio không khớp snapshot.')
            row['audio'] = {'url': f"/api/previews/{job['id']}/{audio['src']}", 'duration': actual}
    usage_path = output / 'token_usage.json'
    usage = json.loads(usage_path.read_text(encoding='utf-8')) if usage_path.is_file() else job.get('tokenUsage')
    snapshot = {'id': job['id'], 'revision': fingerprint, 'renderer': VERSION,
                **job['config'], 'sourceSignature': signature(job['config']),
                'duration': sum(p['duration'] for p in script['phases']),
                'width': 1920, 'height': 1080, 'phases': rows,
                **({'tokenUsage': usage} if usage is not None else {})}
    temporary = output / 'snapshot.tmp'
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(output / 'snapshot.json')
    return snapshot


class GraphicsJobManager(ScriptJobManager):
    def __init__(self, storage: Path):
        super().__init__(storage, kind='graphics', label='đồ họa')
        self.storage = storage

    def create(self, request: GraphicsRequest):
        config = request.model_dump(exclude={'previewOnly'})
        source = self.storage / 'scripts' / request.scriptId
        try:
            script_job = json.loads((source / 'job.json').read_text(encoding='utf-8'))
            if script_job['status'] != 'succeeded':
                raise GraphicsInputError('Kịch bản chưa tạo thành công. Hãy hoàn tất bước 1.')
            if script_job['projectId'] != request.projectId:
                raise GraphicsInputError('Kịch bản không thuộc dự án hiện tại.')
            raw = (source / 'kich_ban.json').read_bytes()
            script = json.loads(raw)
            from plant_kurzge import validate_generated
            errors = validate_generated(script)
            if errors:
                raise GraphicsInputError('JSON kịch bản không hợp lệ. Hãy tạo lại ở bước 1.')
            project_script(script)
        except (OSError, json.JSONDecodeError, KeyError) as error:
            raise GraphicsInputError('Không tìm thấy JSON đầy đủ. Hãy tạo lại kịch bản ở bước 1.') from error
        context = load_render_context(request.styleId, request.categoryId)
        from image_motion_ai import VERSION
        identity = {'config': config, 'script': hashlib.sha256(raw).hexdigest(),
                    'style': context, 'renderer': VERSION}
        if request.previewOnly:
            identity['workflow'] = 'stills-v1'
        key = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.lock:
            if self.stopping:
                raise RuntimeError('Máy chủ đang dừng.')
            previous = []
            for path in self.root.glob('*/job.json'):
                job = json.loads(path.read_text(encoding='utf-8'))
                if job['projectId'] == request.projectId and job['status'] in ACTIVE:
                    return job
                if job.get('key') == key and job['status'] == 'awaiting_confirmation':
                    return job
                if job.get('key') == key and job['status'] == 'failed':
                    previous.append(job)
            retry = max(previous, key=lambda j: j['updatedAt']) if previous else None
            if retry and request.previewOnly:
                try:
                    load_stills(self.storage / 'previews' / retry['id'], complete=bool(retry.get('confirmed')))
                except (OSError, ValueError, KeyError, TypeError):
                    retry = None
            if retry and (not request.previewOnly or retry.get('confirmed')):
                # A worker may finish before publication fails. Validate its saved
                # output before replacing the narrated script or calling AI again.
                output = self.storage / 'previews' / retry['id']
                try:
                    fingerprint = ET.fromstring((output / 'phase_1.svg').read_text(encoding='utf-8')).get('data-fingerprint')
                    if not isinstance(fingerprint, str) or not re.fullmatch(r'[a-f0-9]{64}', fingerprint):
                        raise ValueError('Thiếu fingerprint của lần dựng.')
                    snapshot = completed_snapshot(self.storage, retry, fingerprint)
                except (OSError, ValueError, KeyError, TypeError, ET.ParseError):
                    pass
                else:
                    return self.update(retry['id'], status='succeeded', stage='completed',
                                       completed=len(snapshot['phases']), total=len(snapshot['phases']),
                                       result=snapshot, error=None, key=key)
            job_id = retry['id'] if retry else uuid.uuid4().hex
            directory = self.root / job_id
            # Storage may have been cleaned up since the server started.
            directory.mkdir(parents=True, exist_ok=True)
            output = self.storage / 'previews' / job_id
            output.mkdir(parents=True, exist_ok=True)
            (output / 'kich_ban.json').write_bytes(raw)
            references = source / 'references.json'
            if references.is_file():
                manifest = json.loads(references.read_text(encoding='utf-8'))
                (output / 'references.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
                for item in manifest:
                    target = output / item['src']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source / item['src'], target)
            (output / 'render_config.json').write_text(
                json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
            from character_assets import CharacterAssets
            CharacterAssets(context, output)
            # An incomplete attempt is never served, including after a failed publication.
            (output / 'snapshot.json').unlink(missing_ok=True)
            job = {'id': job_id, 'projectId': request.projectId, 'config': config, 'key': key,
                   'status': 'queued', 'stage': 'queued', 'completed': 0, 'total': 0,
                   'createdAt': retry['createdAt'] if retry else now(), 'updatedAt': now(),
                   'attempt': retry.get('attempt', 1) + 1 if retry else 1,
                   'result': None, 'error': None,
                   **({'tokenUsage': retry['tokenUsage']} if retry and 'tokenUsage' in retry else {})}
            if request.previewOnly:
                job.update(workflow='stills-v1', confirmed=bool(retry and retry.get('confirmed')),
                           sourceSignature=signature(config), previews=load_stills(output))
            self.write(job_id, job)
            self.executor.submit(self.run, job_id)
            return job

    def confirm(self, job_id):
        with self.lock:
            job = self.read(job_id)
            if job.get('workflow') != 'stills-v1':
                raise GraphicsInputError('Tác vụ này không có bước duyệt ảnh tĩnh.')
            if job.get('confirmed') and job['status'] in (*ACTIVE, 'succeeded'):
                return job
            if job['status'] != 'awaiting_confirmation' and not (
                    job['status'] == 'failed' and job.get('confirmed')):
                raise GraphicsInputError('Ảnh preview chưa sẵn sàng để xác nhận.')
            if self.stopping:
                raise RuntimeError('Máy chủ đang dừng.')
            for path in self.root.glob('*/job.json'):
                other = json.loads(path.read_text(encoding='utf-8'))
                if other['id'] != job_id and other['projectId'] == job['projectId'] and other['status'] in ACTIVE:
                    raise GraphicsInputError('Dự án đang có tác vụ đồ họa khác. Hãy chờ hoàn tất.')
            output = self.storage / 'previews' / job_id
            try:
                previews = load_stills(output, complete=True)
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise GraphicsInputError('Ảnh preview thiếu hoặc không hợp lệ. Hãy tạo lại đồ họa.') from error
            job = self.update(job_id, confirmed=True, status='queued', stage='queued',
                              completed=0, total=0, error=None, previews=previews)
            self.executor.submit(self.run, job_id)
            return job

    def run(self, job_id):
        process = None
        try:
            directory = self.root / job_id
            output = self.storage / 'previews' / job_id
            job = self.read(job_id)
            mode = 'stills' if job.get('workflow') == 'stills-v1' and not job.get('confirmed') else 'complete'
            with (directory / 'worker.log').open('a', encoding='utf-8') as log:
                with self.lock:
                    if self.stopping:
                        return
                    self.update(job_id, status='running', stage='preparing')
                    process = subprocess.Popen(
                        [sys.executable, '-u', '-m', 'backend.graphics_worker', str(output), mode],
                        cwd=ROOT, stdout=subprocess.PIPE, stderr=log,
                        text=True, encoding='utf-8', start_new_session=True)
                    self.process = process
                outcome = None
                for line in process.stdout:
                    event = json.loads(line)
                    if isinstance(event.get('tokenUsage'), dict):
                        self.update(job_id, tokenUsage=event['tokenUsage'])
                    if event.get('stage') in ('preparing', 'narration', 'synchronizing', 'images', 'phases', 'checking', 'stills'):
                        self.update(job_id, stage=event['stage'], completed=event.get('completed', 0),
                                    total=event.get('total', 0),
                                    **({'previews': load_stills(output)} if event['stage'] == 'stills' else {}))
                    if event.get('status') in ('succeeded', 'failed'):
                        outcome = event
                code = process.wait()
            if not outcome or code != 0:
                raise RuntimeError('Tiến trình dựng đồ họa đã dừng.')
            if outcome['status'] == 'failed':
                self.update(job_id, status='failed', stage='failed', error=outcome['error'])
            elif mode == 'stills':
                previews = load_stills(output, complete=True)
                self.update(job_id, status='awaiting_confirmation', stage='awaiting_confirmation',
                            previews=previews, completed=len(previews), total=len(previews), error=None)
            else:
                job = self.read(job_id)
                snapshot = completed_snapshot(self.storage, job, outcome['fingerprint'])
                self.update(job_id, status='succeeded', stage='completed', result=snapshot, error=None)
        except Exception:
            diagnostic = traceback.format_exc()
            try:
                with (self.root / job_id / 'worker.log').open('a', encoding='utf-8') as log:
                    log.write(diagnostic)
            except OSError:
                sys.stderr.write(diagnostic)
            self.update(job_id, status='failed', stage='failed', result=None,
                        error='Không thể hoàn tất hoặc lưu đồ họa. Hãy thử lại ở mục 2.')
        finally:
            if process is not None:
                JobManager.kill_process(process)
                process.wait()
                process.stdout.close()
            with self.lock:
                if self.process is process:
                    self.process = None
