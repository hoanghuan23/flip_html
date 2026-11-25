import copy
import io
from importlib.metadata import PackageNotFoundError
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.inputs import attach_voiceover, split_input
from backend.models import GraphicsRequest
from backend.narration import get_tts, prepare_narration, synthesize, tts_config
from backend.graphics import completed_snapshot
from backend.test_scripts import ACCEPTED, screenplay
from backend.script_worker import run as script_worker
from render_style import load_render_style
from render_hyperframes import PreviewError, collect_scenes, prepare_project, verify_video
from three_motion import build_preview, validate_plan, verify_phases


def reference(directory, number=2):
    # Local renderer fixture; input images are no longer accepted by the API.
    path = directory / 'assets/references/photo.png'
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (24, 16), '#3766ab').save(path, format='PNG')
    rows = [{'id': 'photo', 'name': 'Vệ tinh.png', 'number': number,
             'src': path.relative_to(directory).as_posix()}]
    (directory / 'references.json').write_text(json.dumps(rows))
    return rows


def mesh_plan(duration=2):
    return {'nodes': [{'id': 'satellite', 'geometry': 'box', 'scale': [.5, .8, .2]},
                      {'id': 'earth', 'geometry': 'sphere', 'position': [-2, -4, -5], 'scale': [3]*3}],
            'camera': [{'t': 0, 'position': [0, 1, 9]}, {'t': duration, 'position': [0, 1, 7]}],
            'tracks': [{'target': 'satellite', 'property': 'position',
                        'keys': [{'t': 0, 'value': [-1, 0, 0]}, {'t': duration, 'value': [1, 0, 0]}]}],
            'overlays': [{'type': 'image', 'number': 2, 'start': .2, 'end': duration},
                         {'type': 'connector', 'text': '550 km', 'target': 'satellite', 'endTarget': 'earth',
                          'start': .5, 'end': duration, 'cue': '550'}]}


def alignment(text, duration=1.7):
    return {'characters': list(text), 'character_start_times_seconds': [i / len(text)*duration for i in range(len(text))],
            'character_end_times_seconds': [(i+1)/len(text)*duration for i in range(len(text))]}


class NarratedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1.7',
                                 '-f', 'wav', 'pipe:1'], check=True, capture_output=True)
        cls.wav = result.stdout

    def setUp(self):
        get_tts.cache_clear()
        self.addCleanup(get_tts.cache_clear)
        self.version = patch('backend.narration.version', return_value='3.8.5')
        self.version.start()
        self.addCleanup(self.version.stop)

    def engine(self):
        tts = Mock()
        tts.save.side_effect = lambda audio, path: Path(path).write_bytes(self.wav)
        return patch('backend.narration.get_tts', return_value=tts)

    def config(self):
        return patch.dict('os.environ', {'VIENEU_VOICE': ''})

    def test_sections_and_consecutive_voice_segments_are_lossless(self):
        source = 'Vệ tinh\nMô tả:\nCamera tiến gần.\nThuyết minh:\n“Câu một.\nCâu hai.”'
        visual, voice = split_input(source)
        self.assertEqual(visual, 'Vệ tinh\n\nCamera tiến gần.')
        self.assertEqual(voice, 'Câu một.\nCâu hai.')
        script = {'phases': [{'voiceover': 'Câu một.'}, {'voiceover': 'Câu hai.'}]}
        attach_voiceover(script, voice)
        self.assertEqual(''.join(p['voiceover'] for p in script['phases']), voice)
        for pieces in (['Câu hai.', 'Câu một.'], ['Câu một.', 'Câu khác.'], ['Câu một.']):
            with self.assertRaises(ValueError):
                attach_voiceover({'phases': [{'voiceover': p} for p in pieces]}, voice)
        self.assertEqual(split_input('Văn bản thường'), ('Văn bản thường', ''))
        with self.assertRaisesRegex(ValueError, 'trống'):
            split_input('Mô tả: Cảnh\nThuyết minh:\n')

    def test_script_worker_preserves_speech_and_ignores_reference_metadata(self):
        script = screenplay()
        script['phases'][0]['voiceover'] = 'Độ cao 550 km.'
        with tempfile.TemporaryDirectory() as temporary, patch.multiple('plant_kurzge', API_URL='test', API_KEY='test', MODEL='test'):
            directory = Path(temporary)
            (directory / 'input.txt').write_text('Vệ tinh\nMô tả:\nDùng Hình 2.\nThuyết minh:\nĐộ cao 550 km.')
            reference(directory)
            with patch('plant_kurzge.request_text', side_effect=[ACCEPTED, json.dumps(script)]) as api, patch('sys.stdout', new_callable=io.StringIO):
                script_worker(directory)
            saved = json.loads((directory / 'kich_ban.json').read_text())
            self.assertEqual(saved['voiceoverText'], 'Độ cao 550 km.')
            self.assertIn('voiceover', api.call_args.args[0])
            self.assertNotIn('REFERENCE IMAGES', api.call_args.args[0])
            self.assertNotIn('assets/references', api.call_args.args[0])

    def test_tts_cache_and_invalid_cache_regeneration(self):
        with tempfile.TemporaryDirectory() as temporary, self.config(), self.engine() as factory:
            directory = Path(temporary)
            path, metadata = synthesize('Độ cao 550 km.', directory)
            synthesize('Độ cao 550 km.', directory, previous_text='Cảnh trước.', next_text='Cảnh sau.')
            tts = factory.return_value
            tts.infer.assert_called_once_with(text='Độ cao 550 km.', voice='Hải Đăng')
            self.assertEqual(factory.call_count, 1)
            self.assertEqual(path.suffix, '.wav')
            self.assertAlmostEqual(metadata['duration'], 1.7, places=2)
            self.assertEqual(metadata['provider'], 'vieneu')
            self.assertIsNone(metadata['alignment'])
            path.write_bytes(b'broken')
            synthesize('Độ cao 550 km.', directory)
            self.assertEqual(tts.infer.call_count, 2)
            metadata_path = path.with_suffix('.json')
            saved = json.loads(metadata_path.read_text())
            saved['duration'] += 1
            metadata_path.write_text(json.dumps(saved))
            synthesize('Độ cao 550 km.', directory)
            self.assertEqual(tts.infer.call_count, 3)
            with patch.dict('os.environ', {'VIENEU_VOICE': 'Minh Quân'}):
                other, _ = synthesize('Độ cao 550 km.', directory)
            self.assertNotEqual(path, other)
            tts.infer.assert_called_with(text='Độ cao 550 km.', voice='Minh Quân')
            with patch('backend.narration.version', return_value='3.8.6'):
                upgraded, _ = synthesize('Độ cao 550 km.', directory)
            self.assertNotEqual(path, upgraded)

    def test_tts_model_is_loaded_once_and_initialization_errors_are_clear(self):
        module = Mock()
        with patch.dict('sys.modules', {'vieneu': module}):
            self.assertIs(get_tts(), get_tts())
            module.Vieneu.assert_called_once_with()
            get_tts.cache_clear()
            module.Vieneu.side_effect = RuntimeError('model unavailable')
            with self.assertRaisesRegex(ValueError, 'khởi tạo được VieNeu'):
                get_tts()
        with patch('backend.narration.version', side_effect=PackageNotFoundError):
            with self.assertRaisesRegex(ValueError, 'pip install'):
                tts_config()

    def test_tts_errors_do_not_publish_broken_audio_or_metadata(self):
        with tempfile.TemporaryDirectory() as temporary, self.config(), self.engine() as factory:
            directory = Path(temporary)
            tts = factory.return_value
            tts.infer.side_effect = RuntimeError('internal model error')
            with self.assertRaisesRegex(ValueError, 'VIENEU_VOICE'):
                synthesize('text', directory)
            tts.infer.side_effect = None
            tts.save.side_effect = lambda audio, path: Path(path).write_bytes(b'broken wav')
            with self.assertRaisesRegex(ValueError, 'ffprobe'):
                synthesize('text', directory)
            self.assertEqual(list(directory.iterdir()), [])
            tts.save.side_effect = OSError('disk full')
            with self.assertRaisesRegex(ValueError, 'cache'):
                synthesize('text', directory)
            self.assertEqual(list(directory.iterdir()), [])

    def test_measured_audio_flows_to_3d_snapshot_and_export(self):
        text = 'Độ cao 550 km.'
        with tempfile.TemporaryDirectory() as temporary, self.config(), self.engine():
            storage = Path(temporary)
            output = storage / 'previews' / ('b'*32)
            output.mkdir(parents=True)
            script = screenplay()
            script['phases'][0]['voiceover'] = text
            script['phases'][0]['actions'][0]['cue'] = '550'
            original = copy.deepcopy(script['phases'][0])
            refs = reference(output)
            prepare_narration(script, output, storage / 'cache')
            phase = script['phases'][0]
            self.assertLess(phase['duration'], 2)
            self.assertAlmostEqual(phase['duration'] * 30, round(phase['duration'] * 30))
            self.assertAlmostEqual(phase['actions'][0]['start'],
                                   original['actions'][0]['start'] / original['duration'] * phase['duration'])
            (output / 'kich_ban.json').write_text(json.dumps(script))
            context = load_render_style('3d-motion-infographic')
            (output / 'render_config.json').write_text(json.dumps(context))
            def generate(_):
                self.assertIn('Omit every cue field', _)
                plan = mesh_plan(phase['duration'])
                plan['overlays'][1].pop('cue')
                return json.dumps(plan)
            revision = build_preview(script, output, generate, style_context=context, references=refs)
            config = {'projectId': 'test', 'scriptId': 'a'*32, 'categoryId': '3D', 'styleId': context['id']}
            snapshot = completed_snapshot(storage, {'id': output.name, 'config': config}, revision)
            self.assertEqual(snapshot['renderer'], 'three-motion-v1')
            self.assertEqual(snapshot['phases'][0]['duration'], phase['duration'])
            self.assertIn('/assets/audio/', snapshot['phases'][0]['audio']['url'])
            self.assertTrue(snapshot['phases'][0]['audio']['url'].endswith('.wav'))
            scenes = collect_scenes([output])
            self.assertEqual(scenes[0].kind, 'three')
            manifest = prepare_project(scenes, storage / 'export', 30)
            self.assertEqual(manifest['audio'], 'voiceover')
            exported = (storage / 'export/index.html').read_text()
            self.assertEqual(exported.count('<audio '), 1)
            self.assertNotIn('https://', exported)
            with TestClient(create_app(storage)) as client:
                self.assertEqual(client.get(snapshot['phases'][0]['audio']['url']).status_code, 200)
                self.assertEqual(client.get(f'/api/previews/{output.name}/assets/runtime/three-scene.js').status_code, 200)
                self.assertEqual(client.get(f'/api/previews/{output.name}/assets/../../.env').status_code, 404)
            # Audio failure must invalidate the snapshot instead of publishing silently.
            (output / phase['audio']['src']).unlink()
            with self.assertRaises(ValueError):
                completed_snapshot(storage, {'id': output.name, 'config': config}, revision)

    def test_scene_validation_catches_broken_graph_timing_and_reference(self):
        phase = {'duration': 2}
        raw = mesh_plan()
        raw['overlays'][1].pop('cue')
        validate_plan(raw, phase, [{'number': 2}])
        broken = []
        p = copy.deepcopy(raw); p['nodes'][0]['parent'] = 'missing'; broken.append(p)
        p = copy.deepcopy(raw); p['nodes'][0]['parent'] = 'earth'; p['nodes'][1]['parent'] = 'satellite'; broken.append(p)
        p = copy.deepcopy(raw); p['camera'][1]['t'] = 3; broken.append(p)
        p = copy.deepcopy(raw); p['tracks'][0]['keys'][1]['t'] = 0; broken.append(p)
        p = copy.deepcopy(raw); p['overlays'][0]['number'] = 7; broken.append(p)
        p = copy.deepcopy(raw); p['nodes'][0]['position'] = [float('nan'), 0, 0]; broken.append(p)
        for value in broken:
            with self.assertRaises(ValueError):
                validate_plan(value, phase, [{'number': 2}])
        phase['description'] = 'Kèm dòng chữ "Quỹ đạo thấp – khoảng 550 km".'
        with self.assertRaisesRegex(ValueError, 'nguyên văn'):
            validate_plan(raw, phase, [{'number': 2}])

    def test_three_timing_repairs_use_measured_duration_alignment_and_rejected_response(self):
        duration = 115 / 30
        script = screenplay()
        phase = script['phases'][0]
        phase.update(duration=duration, voiceover='một hai', audio={'alignment': 'alignment.json'})
        script['total_duration'] = duration
        valid = mesh_plan(duration)
        valid['overlays'] = []
        outside = copy.deepcopy(valid)
        outside['camera'][1]['t'] = 4
        duplicate = copy.deepcopy(valid)
        duplicate['camera'][1]['cue'] = 'một'
        responses = [json.dumps(plan, ensure_ascii=False) for plan in [outside, duplicate, valid]]
        context = load_render_style('3d-motion-infographic')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'alignment.json').write_text(json.dumps({'alignment': alignment(phase['voiceover'], 3)}))
            with patch('plant_kurzge.request_text', side_effect=responses) as request:
                revision = build_preview(script, output, request, style_context=context)
            self.assertEqual(request.call_count, 3)
            first, second, third = [call.args[0] for call in request.call_args_list]
            schema = json.loads(first.split('\nJSON SCHEMA:\n')[1].split('\nGeometry units:')[0])
            for model, fields in [('CameraKey', ['t']), ('Keyframe', ['t']), ('Overlay', ['start', 'end'])]:
                for field in fields:
                    self.assertEqual(schema['$defs'][model]['properties'][field]['maximum'], duration)
            speech = json.loads(first.split('\nSPEECH WORD TIMES (seconds within this phase):\n')[1].split('\nFULL SCRIPT CONTEXT:')[0])
            self.assertEqual([word['text'] for word in speech], ['một', 'hai'])
            self.assertEqual(speech[0]['t'], 0)
            self.assertGreater(speech[1]['t'], 0)
            self.assertIn(responses[0], second)
            self.assertIn('camera[1].t=4.0', second)
            self.assertIn(responses[1], third)
            self.assertIn('camera[0].t=0.0 >= camera[1].t=0.0', third)
            for attempt, response in enumerate(responses, 1):
                self.assertEqual((output / 'prompts' / f'phase_1_3d_response_{attempt}.txt').read_text(), response)
            self.assertEqual(verify_phases(output, script, revision)[0]['duration'], duration)
            self.assertEqual(build_preview(script, output, lambda _: self.fail('Valid cache must be reused'),
                                           style_context=context), revision)

    def test_three_timing_failure_keeps_diagnostic_without_publishing_phase(self):
        script = screenplay()
        phase = script['phases'][0]
        raw = mesh_plan(phase['duration'])
        raw['overlays'] = []
        raw['tracks'][0]['keys'][1]['t'] = 0
        response = json.dumps(raw)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with self.assertRaisesRegex(ValueError, r'Cảnh 3D 1.*tracks\[0\].*satellite.position'):
                build_preview(script, output, lambda _: response, style_context=load_render_style('3d-motion-infographic'))
            self.assertTrue((output / 'prompts/phase_1_3d_response_3.txt').is_file())
            self.assertFalse((output / 'phase_1.html').exists())
            self.assertFalse((output / 'phase_1.scene.json').exists())

    def test_legacy_worker_preserves_script_bytes_and_does_not_call_tts(self):
        from backend.graphics_worker import run
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = json.dumps(screenplay(), ensure_ascii=False, indent=4) + '\n'
            (directory / 'kich_ban.json').write_text(original)
            (directory / 'render_config.json').write_text(json.dumps(load_render_style('flat')))
            with patch.multiple('plant_kurzge', API_URL='test', API_KEY='test', MODEL='test'), \
                    patch('backend.graphics_worker.image_config', return_value={'key': 'test'}), \
                    patch('backend.graphics_worker.build_preview', return_value='fingerprint'), \
                    patch('backend.narration.synthesize') as tts, patch('sys.stdout', new_callable=io.StringIO) as events:
                run(directory)
            self.assertEqual((directory / 'kich_ban.json').read_text(), original)
            self.assertEqual(json.loads(events.getvalue().splitlines()[-1])['status'], 'succeeded')
            tts.assert_not_called()

    def test_text_mentions_need_no_images_and_legacy_image_fields_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary, TestClient(create_app(Path(temporary))) as client, \
                patch.object(client.app.state.scripts.executor, 'submit'):
            for project, extra in [('text-only', {}), ('legacy', {'referenceImages': [{'dataUrl': 'invalid'}]})]:
                with self.subTest(project=project):
                    response = client.post('/api/scripts', json={
                        'projectId': project, 'content': 'Sử dụng Hình 7', **extra})
                    self.assertEqual(response.status_code, 202)
                    directory = Path(temporary) / 'scripts' / response.json()['id']
                    self.assertEqual((directory / 'input.txt').read_text(), 'Sử dụng Hình 7')
                    self.assertFalse((directory / 'references.json').exists())
                    self.assertFalse((directory / 'assets').exists())

    def test_mp4_verification_requires_narration_stream(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'video.mp4'
            output.write_bytes(b'fixture')
            video = {'format': {'duration': '2'}, 'streams': [{'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}]}
            with patch('render_hyperframes.subprocess.run') as run:
                run.side_effect = [unittest.mock.Mock(stdout=json.dumps(video)), unittest.mock.Mock(stdout='{"streams":[]}')]
                with self.assertRaisesRegex(PreviewError, 'âm thanh'):
                    verify_video(output, 2, 30, 1920, 1080, expected_audio=True)


if __name__ == '__main__':
    unittest.main()
