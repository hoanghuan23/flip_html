import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.jobs import JobManager
from backend.models import ExportConfig, ExportRequest
from render_hyperframes import PreviewError, verify_video

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.no_render = patch.object(JobManager, 'render', return_value=None)
        self.no_render.start()
        self.addCleanup(self.no_render.stop)
        self.client = TestClient(create_app(self.root))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def preview(self):
        snapshot_id = 'a' * 32
        directory = self.root / 'previews' / snapshot_id
        directory.mkdir(exist_ok=True)
        source = '<html><head></head><body><svg viewBox="0 0 1920 1080"></svg><script>var D=2;window.renderAt=function(t){};</script></body></html>'
        (directory / 'phase_1.html').write_text(source)
        playlist = [{'src': 'phase_1.html', 'title': 'Cảnh', 'duration': 2}]
        (directory / 'index.html').write_text('<script type="application/json" id="data">' + json.dumps(playlist) + '</script>')
        snapshot = {'id': snapshot_id, 'revision': hashlib.sha256(source.encode()).hexdigest(),
                    'duration': 2, 'width': 1920, 'height': 1080,
                    'phases': [{'id': '1', 'name': 'Cảnh', 'duration': 2,
                                'url': f'/api/previews/{snapshot_id}/phase_1.html'}]}
        (directory / 'snapshot.json').write_text(json.dumps(snapshot))
        return snapshot

    def test_empty_configuration_keeps_preview_and_export_routes(self):
        snapshot = self.preview()
        self.assertEqual(self.client.get('/api/previews/' + snapshot['id']).json(), snapshot)
        self.assertEqual(self.client.get(snapshot['phases'][0]['url']).status_code, 200)
        for path in ['/api/previews', '/api/scripts', '/api/graphics', '/api/graphics/' + 'b' * 32 + '/confirm']:
            response = self.client.post(path, json={})
            self.assertEqual(response.status_code, 503)
            self.assertIn('Chưa có cấu hình', response.json()['detail'])
        self.assertEqual(self.client.get('/api/styles/flat/preview').status_code, 404)
        self.assertFalse(hasattr(self.client.app.state, 'graphics'))
        self.assertFalse(hasattr(self.client.app.state, 'scripts'))

    def export(self, snapshot, **config):
        return self.client.post('/api/exports', json={'snapshotId': snapshot['id'], 'config': config})

    def test_export_config_validation_and_deduplication(self):
        snapshot = self.preview()
        for config in [{'fps': 15}, {'quality': 'other'}, {'filename': '../outside'}, {'filename': '\n'}]:
            self.assertEqual(self.export(snapshot, **config).status_code, 422)
        first = self.export(snapshot)
        self.assertEqual(first.status_code, 202)
        job = first.json()
        self.assertEqual(self.export(snapshot).json()['id'], job['id'])
        self.assertEqual(job['config']['filename'], 'video-cua-toi.mp4')
        self.assertEqual(self.client.get('/api/exports/'+job['id']+'/video').status_code, 409)

    def test_missing_snapshots_jobs_and_paths(self):
        unknown = 'a'*32
        self.assertEqual(self.client.post('/api/exports', json={'snapshotId': unknown, 'config': {}}).status_code, 404)
        self.assertEqual(self.client.get('/api/exports/'+unknown).status_code, 404)
        self.assertEqual(self.client.get('/api/previews/not-an-id').status_code, 404)
        snapshot = self.preview()
        self.assertEqual(self.client.get('/api/previews/'+snapshot['id']+'/draft.json').status_code, 404)

    def test_export_recreates_removed_output_root_without_changing_preview(self):
        snapshot = self.preview()
        source = self.root / 'previews' / snapshot['id']
        before = {path.name: path.read_bytes() for path in source.iterdir()}
        (self.root / 'exports').rmdir()
        response = self.export(snapshot)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertTrue((self.root / 'exports' / response.json()['id'] / 'job.json').is_file())
        self.assertEqual({path.name: path.read_bytes() for path in source.iterdir()}, before)
        self.assertEqual(self.client.get('/api/previews/'+snapshot['id']).status_code, 200)

    def test_export_storage_errors_do_not_claim_preview_is_missing(self):
        snapshot = self.preview()
        for error in (FileNotFoundError('export storage removed'), PermissionError('not writable')):
            with self.subTest(error=type(error).__name__), patch.object(
                    self.client.app.state.jobs, 'write', side_effect=error):
                response = self.export(snapshot)
            self.assertEqual(response.status_code, 503, response.text)
            self.assertIn('lưu tác vụ xuất video', response.json()['detail'])
            self.assertNotIn('Preview không còn', response.json()['detail'])

    def test_video_range_and_attachment_use_the_same_file(self):
        job = self.export(self.preview(), filename='Câu chuyện').json()
        output = self.root / 'exports' / job['id'] / 'video.mp4'
        output.write_bytes(b'0123456789'*100)
        self.client.app.state.jobs.update(job['id'], status='succeeded')
        response = self.client.get('/api/exports/'+job['id']+'/video', headers={'Range': 'bytes=5-14'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b'5678901234')
        self.assertEqual(response.headers['content-type'], 'video/mp4')
        self.assertTrue(response.headers['content-disposition'].startswith('inline'))
        download = self.client.get('/api/exports/'+job['id']+'/download')
        self.assertTrue(download.headers['content-disposition'].startswith('attachment'))
        self.assertEqual(len(download.content), 1000)
        output.unlink()
        self.assertEqual(self.client.get('/api/exports/'+job['id']+'/video').status_code, 404)

    def test_restart_marks_incomplete_jobs_failed_but_preserves_success(self):
        snapshot = self.preview()
        complete = self.export(snapshot).json()
        self.client.app.state.jobs.update(complete['id'], status='succeeded')
        job = self.export(snapshot, fps=24).json()
        # A fresh manager emulates startup after a crash, reading persisted metadata.
        restored = JobManager(self.root)
        try:
            result = restored.read(job['id'])
            self.assertEqual(result['status'], 'failed')
            self.assertIn('khởi động lại', result['error'])
            self.assertEqual(restored.read(complete['id'])['status'], 'succeeded')
            self.assertNotEqual(restored.create(ExportRequest(snapshotId=job['snapshotId'], config=ExportConfig()))['id'], job['id'])
        finally:
            restored.close()



class VerificationTests(unittest.TestCase):
    def test_verifies_actual_duration_size_and_fps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video.mp4'; path.write_bytes(b'fixture')
            metadata = {'format': {'duration': '2'}, 'streams': [{'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}]}
            def verify():
                with patch('render_hyperframes.subprocess.run') as run:
                    run.return_value.stdout = json.dumps(metadata)
                    verify_video(path, 2, 30, 1920, 1080)
            verify()
            for field, value in [('width', 1280), ('avg_frame_rate', '24/1')]:
                saved = metadata['streams'][0][field]; metadata['streams'][0][field] = value
                with self.assertRaises(PreviewError): verify()
                metadata['streams'][0][field] = saved
            metadata['format']['duration'] = '3'
            with self.assertRaises(PreviewError): verify()
