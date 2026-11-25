import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import wave

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.image_store import ImageBinding, ImageUpload, resolve_images, save_image
from backend.illustrations import attach_events, validate_events
from backend.narration import synthesize_at_cues
from map_renderer import _style_url, prepare_map
from render_style import load_render_style
from script_analysis import parse_detailed


class MapImageTests(unittest.TestCase):
    def test_map_2d_basemap_is_selected_by_style(self):
        context = load_render_style('map-2d')
        with patch.dict('os.environ', {'MAP_STYLE_URL': 'https://example.com/other-style'}):
            self.assertEqual(_style_url(context), 'https://tiles.openfreemap.org/styles/liberty')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            plan_path = output / 'map_plan.json'
            plan_path.write_text(json.dumps({'styleUrl': 'https://example.com/other-style'}), encoding='utf-8')
            plan = prepare_map({'phases': []}, output, context, None)
            self.assertEqual(plan['styleUrl'], _style_url(context))
            self.assertIn('OpenFreeMap', plan['attribution'])
        context['preset']['map']['styleUrl'] = 'https://example.com/other-style'
        with self.assertRaisesRegex(ValueError, 'OpenFreeMap'):
            _style_url(context)

    def test_preview_playlist_and_map_runtime_are_served(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            preview = storage / 'previews' / ('a' * 32)
            runtime = preview / 'assets' / 'map'
            runtime.mkdir(parents=True)
            (preview / 'snapshot.json').write_text(json.dumps({'id': 'a' * 32}), encoding='utf-8')
            (preview / 'index.html').write_text('<!doctype html><title>Map</title>', encoding='utf-8')
            (runtime / 'maplibre-gl.css').write_text('body{color:red}', encoding='utf-8')
            with TestClient(create_app(storage)) as client:
                self.assertEqual(client.get('/api/previews/' + 'a' * 32 + '/index.html').status_code, 200)
                self.assertEqual(client.get('/api/previews/' + 'a' * 32 + '/assets/map/maplibre-gl.css').status_code, 200)

    def test_uploaded_original_is_bound_to_project_and_mentioned_number(self):
        stream = io.BytesIO()
        Image.new('RGB', (80, 40), '#aa3344').save(stream, format='PNG')
        data_url = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            upload = ImageUpload(projectId='project-one', number=3, kind='illustration',
                                 filename='photo.png', dataUrl=data_url)
            saved = save_image(storage, upload)
            binding = ImageBinding(number=3, kind='illustration', imageId=saved['id'])
            images = resolve_images(storage, 'project-one', [binding], 'Hiện ảnh @image_3.')
            self.assertEqual(images[0]['path'].read_bytes(), stream.getvalue())
            with self.assertRaisesRegex(ValueError, 'Chưa tải ảnh'):
                resolve_images(storage, 'project-one', [binding], 'Hiện ảnh @image_4.')
            with self.assertRaisesRegex(ValueError, 'không còn trên server'):
                resolve_images(storage, 'another-project', [binding], 'Hiện ảnh @image_3.')

    def test_detailed_plan_resolves_all_eight_cues(self):
        sources = parse_detailed((Path(__file__).resolve().parent.parent / 'plan.md').read_text(encoding='utf-8'))
        script = {'phases': [{'name': source['name'], 'voiceover': source['voiceover']}
                             for source in sources]}
        references = [{'number': i, 'kind': 'illustration'} for i in range(1, 9)]
        attach_events(script, sources, references)
        validate_events(script, references)
        self.assertEqual([e['number'] for phase in script['phases']
                          for e in phase['illustration_events'] if 'number' in e], [1, 2, 7, 8, 5, 6, 3, 4])
        self.assertEqual(script['phases'][2]['illustration_events'][0]['cue'], 'Đại Nội')

    def test_cued_synthesis_has_exact_segment_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)

            def fake_synthesize(text, directory, **_):
                path = directory / f'{len(list(directory.glob("*.wav")))}.wav'
                with wave.open(str(path), 'wb') as wav:
                    wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                    wav.writeframes(b'\0\0' * (800 * len(text)))
                return path, {'duration': len(text) * .1}

            def fake_probe(path):
                with wave.open(str(path), 'rb') as wav:
                    return wav.getnframes() / wav.getframerate()

            with patch('backend.narration.synthesize', side_effect=fake_synthesize), \
                 patch('backend.narration.tts_config', return_value={'provider': 'fake'}), \
                 patch('backend.narration.probe_audio', side_effect=fake_probe):
                audio, metadata = synthesize_at_cues('Chào Nha Trang', ['Nha Trang'], cache)
            self.assertTrue(audio.is_file())
            self.assertAlmostEqual(metadata['cue_times']['Nha Trang'], .5)
            self.assertAlmostEqual(metadata['duration'], 1.4)


if __name__ == '__main__':
    unittest.main()
