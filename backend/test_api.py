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


def draft():
    return {'projectId': 'project-1', 'title': 'Một câu chuyện', 'styleId': 'cartoon',
            'scenes': [{'id': 'one', 'name': 'Biển và mây', 'narration': 'Nước biển ấm.',
                        'description': 'Mây trôi trên biển.', 'duration': 1.5},
                       {'id': 'two', 'name': 'Gió', 'narration': 'Gió thổi.',
                        'description': 'Những dòng khí chuyển động.', 'duration': 2}]}


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
        response = self.client.post('/api/previews', json=draft())
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def export(self, snapshot, **config):
        return self.client.post('/api/exports', json={'snapshotId': snapshot['id'], 'config': config})

    def test_preview_is_immutable_seekable_and_escapes_user_text(self):
        value = draft()
        value['scenes'][0]['narration'] = '<script>alert(1)</script>'
        response = self.client.post('/api/previews', json=value)
        snapshot = response.json()
        self.assertEqual(snapshot['duration'], 3.5)
        self.assertEqual([p['name'] for p in snapshot['phases']], ['Biển và mây', 'Gió'])
        html = self.client.get(snapshot['phases'][0]['url']).text
        self.assertIn('window.renderAt', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertEqual(self.client.get('/api/previews/'+snapshot['id']).json(), snapshot)
        self.assertNotEqual(self.preview()['id'], snapshot['id'])

    def test_rejects_invalid_durations_duplicate_ids_style_and_empty_scenes(self):
        for key, value in [('duration', 0), ('duration', -2), ('duration', 121), ('name', ' '), ('narration', 'x'*2001)]:
            data = draft(); data['scenes'][0][key] = value
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)
        for data in [dict(draft(), scenes=[]), dict(draft(), styleId='unknown')]:
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)
        data = draft(); data['scenes'][1]['id'] = 'one'
        self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)

    def test_category_style_pair_uses_shared_configuration(self):
        data = dict(draft(), categoryId='education', styleId='outlined-cartoon')
        response = self.client.post('/api/previews', json=data)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIn('#78ccc4', self.client.get(response.json()['phases'][0]['url']).text)
        data['styleId'] = 'flat'
        self.assertEqual(self.client.post('/api/previews', json=data).status_code, 201)
        data['categoryId'] = 'technology'
        self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)
        data['styleId'] = 'isometric-mono'
        self.assertEqual(self.client.post('/api/previews', json=data).status_code, 201)
        data['categoryId'] = 'unknown'
        self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)

    def test_preview_validation_uses_current_style_config(self):
        path = self.root / 'style_config.json'
        config = {'categories': {'science': {'label': 'Tên ban đầu',
                  'allowed_styles': ['detailed-vector', 'flat']}},
                  'default_style': 'detailed-vector'}
        with patch('backend.models.STYLE_CONFIG_PATH', path):
            path.write_text(json.dumps(config), encoding='utf-8')
            data = dict(draft(), categoryId='science', styleId='flat')
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 201)
            config['categories']['science'] = {'label': 'Tên vừa đổi',
                                             'allowed_styles': ['detailed-vector']}
            path.write_text(json.dumps(config), encoding='utf-8')
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)
            path.write_text('{invalid', encoding='utf-8')
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)

    def test_new_configured_styles_create_preview_and_keep_draft_style(self):
        path = self.root / 'style_config.json'
        styles = ['flat', 'flat-with-black', 'halftone-line', 'future-style']
        config = {'categories': {'news_current_affairs': {
            'label': 'Thời sự - tin tức', 'allowed_styles': styles}}, 'default_style': 'flat'}
        path.write_text(json.dumps(config), encoding='utf-8')
        with patch('backend.models.STYLE_CONFIG_PATH', path):
            for style in styles:
                data = dict(draft(), categoryId='news_current_affairs', styleId=style)
                response = self.client.post('/api/previews', json=data)
                self.assertEqual(response.status_code, 201, response.text)
                snapshot = response.json()
                saved = json.loads((self.root / 'previews' / snapshot['id'] / 'draft.json').read_text())
                self.assertEqual(saved['styleId'], style)
                self.assertIn('window.renderAt', self.client.get(snapshot['phases'][0]['url']).text)
            data['styleId'] = 'not-configured'
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)
            data['styleId'] = '../flat'
            self.assertEqual(self.client.post('/api/previews', json=data).status_code, 422)

    def test_style_sample_serves_demo_html_and_leaves_missing_samples_empty(self):
        # Use a separate skills directory; never modify the user's demos.
        sample_root = self.root / 'sample-project'
        with patch('backend.app.ROOT', sample_root):
            app = create_app(self.root / 'sample-storage')
        with TestClient(app) as client:
            endpoint = '/api/styles/outlined-cartoon/preview'
            self.assertEqual(client.get(endpoint).json(), {'url': None})
            demo = sample_root / 'skills' / 'outlined-cartoon' / 'demo' / 'index.html'
            demo.parent.mkdir(parents=True)
            # An image alone no longer counts as a demo.
            (demo.parent / 'preview.png').write_bytes(b'png sample')
            self.assertEqual(client.get(endpoint).json(), {'url': None})
            demo.write_text('<!doctype html><h1>Outlined cartoon</h1>', encoding='utf-8')
            metadata = client.get(endpoint)
            self.assertEqual(metadata.headers['cache-control'], 'no-store')
            demo_url = metadata.json()['url']
            self.assertEqual(demo_url, '/api/styles/outlined-cartoon/demo/index.html')
            response = client.get(demo_url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['content-type'].startswith('text/html'))
            self.assertEqual(response.content, demo.read_bytes())
            demo.unlink()
            self.assertEqual(client.get(endpoint).json(), {'url': None})
            self.assertEqual(client.get(demo_url).status_code, 404)
            self.assertEqual(client.get('/api/styles/outlined-cartoon/demo/PROMPT.md').status_code, 404)
            self.assertEqual(client.get('/api/styles/unknown/preview').status_code, 404)
            self.assertEqual(client.get('/api/styles/unknown/demo/index.html').status_code, 404)

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


if __name__ == '__main__':
    unittest.main()
