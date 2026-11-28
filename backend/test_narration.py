"""VieNeu tests ported from main without the removed graphics renderers."""
import copy
import io
from importlib.metadata import PackageNotFoundError
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from backend.narration import get_tts, prepare_narration, probe_audio, synthesize, tts_config
from backend.test_scripts import screenplay
from generate_audio import generate_audio, main


class NarrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as output:
            output.setparams((1, 2, 1000, 0, 'NONE', 'not compressed'))
            output.writeframes(b'\x00\x00' * 1710)
        cls.wav = buffer.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        get_tts.cache_clear()
        self.addCleanup(get_tts.cache_clear)
        settings = patch.dict('os.environ', {'VIENEU_VOICE': ''})
        settings.start()
        self.addCleanup(settings.stop)
        version = patch('backend.narration.version', return_value='3.8.5')
        version.start()
        self.addCleanup(version.stop)

    def engine(self):
        tts = Mock()
        tts.save.side_effect = lambda audio, path: Path(path).write_bytes(self.wav)
        return patch('backend.narration.get_tts', return_value=tts)

    def test_tts_cache_and_invalid_cache_regeneration(self):
        with self.engine() as factory:
            path, metadata = synthesize('Độ cao 550 km.', self.root)
            synthesize('Độ cao 550 km.', self.root, previous_text='Cảnh trước.', next_text='Cảnh sau.')
            tts = factory.return_value
            tts.infer.assert_called_once_with(text='Độ cao 550 km.', voice='Hải Đăng')
            self.assertEqual(factory.call_count, 1)
            self.assertEqual(path.suffix, '.wav')
            self.assertAlmostEqual(metadata['duration'], 1.71)
            self.assertEqual(metadata['provider'], 'vieneu')
            self.assertIsNone(metadata['alignment'])
            path.write_bytes(b'broken')
            synthesize('Độ cao 550 km.', self.root)
            self.assertEqual(tts.infer.call_count, 2)
            metadata_path = path.with_suffix('.json')
            saved = json.loads(metadata_path.read_text())
            saved['duration'] += 1
            metadata_path.write_text(json.dumps(saved))
            synthesize('Độ cao 550 km.', self.root)
            self.assertEqual(tts.infer.call_count, 3)
            with patch.dict('os.environ', {'VIENEU_VOICE': 'Minh Quân'}):
                other, _ = synthesize('Độ cao 550 km.', self.root)
            self.assertNotEqual(path, other)
            tts.infer.assert_called_with(text='Độ cao 550 km.', voice='Minh Quân')
            with patch('backend.narration.version', return_value='3.8.6'):
                upgraded, _ = synthesize('Độ cao 550 km.', self.root)
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
        with self.engine() as factory:
            tts = factory.return_value
            tts.infer.side_effect = RuntimeError('internal model error')
            with self.assertRaisesRegex(ValueError, 'VIENEU_VOICE'):
                synthesize('text', self.root)
            tts.infer.side_effect = None
            tts.save.side_effect = lambda audio, path: Path(path).write_bytes(b'broken wav')
            with self.assertRaisesRegex(ValueError, 'ffprobe'):
                synthesize('text', self.root)
            self.assertEqual(list(self.root.iterdir()), [])
            tts.save.side_effect = OSError('disk full')
            with self.assertRaisesRegex(ValueError, 'cache'):
                synthesize('text', self.root)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_measured_audio_updates_timeline_and_preserves_unvoiced_scenes(self):
        script = screenplay()
        phase = script['phases'][0]
        unvoiced = copy.deepcopy(phase)
        unvoiced['id'] = 2
        script['phases'].append(unvoiced)
        phase['voiceover'] = 'Mây bay.'
        phase['actions'][0]['start'] = 2
        phase['actions'][0]['cue'] = 'Mây'
        original = copy.deepcopy(phase)
        progress = Mock()
        output = self.root / 'output'
        with self.engine():
            prepare_narration(script, output, self.root / 'cache', progress)
        self.assertAlmostEqual(phase['duration'], math.ceil(1.71 * 30) / 30)
        self.assertAlmostEqual(phase['actions'][0]['start'], 2 / original['duration'] * phase['duration'])
        self.assertAlmostEqual(phase['actions'][0]['end'], phase['duration'])
        self.assertEqual(script['phases'][1], unvoiced)
        self.assertAlmostEqual(script['total_duration'], phase['duration'] + unvoiced['duration'])
        audio = output / phase['audio']['src']
        self.assertEqual(audio.read_bytes(), self.wav)
        self.assertAlmostEqual(probe_audio(audio), 1.71)
        self.assertIsNone(json.loads((output / phase['audio']['alignment']).read_text())['alignment'])
        self.assertEqual(progress.call_args_list[0].args, ('narration', 0, 2))
        self.assertEqual(progress.call_args_list[-1].args, ('narration', 1, 2))

    def test_illustration_cues_use_stitched_audio_boundaries(self):
        script = screenplay()
        phase = script['phases'][0]
        phase['voiceover'] = 'Xin chào. Mây bay. Mưa rơi.'
        phase['illustration_events'] = [
            {'operation': 'show', 'cue': 'Mây'},
            {'operation': 'replace', 'cue': 'Mưa'},
            {'operation': 'hide', 'fraction': .1},
        ]
        output = self.root / 'output'
        with self.engine() as factory:
            prepare_narration(script, output, self.root / 'cache')
            texts = [call.kwargs['text'] for call in factory.return_value.infer.call_args_list]
            self.assertEqual(texts, ['Xin chào. ', 'Mây bay. ', 'Mưa rơi.'])
            repeated = copy.deepcopy(script)
            prepare_narration(repeated, output, self.root / 'cache')
            self.assertEqual(repeated['phases'][0]['illustration_events'], phase['illustration_events'])
            self.assertEqual(factory.return_value.infer.call_count, 3)
        events = phase['illustration_events']
        self.assertEqual([event['operation'] for event in events], ['hide', 'show', 'replace'])
        self.assertAlmostEqual(events[0]['time'], phase['duration'] * .1)
        self.assertAlmostEqual(events[1]['time'], 1.71)
        self.assertAlmostEqual(events[2]['time'], 3.42)
        self.assertAlmostEqual(probe_audio(output / phase['audio']['src']), 5.13)

    def test_narration_duration_limits(self):
        script = screenplay()
        script['phases'][0]['voiceover'] = 'Mây bay.'
        audio = self.root / 'fixture.wav'
        audio.write_bytes(self.wav)
        metadata = {'duration': 120.01, 'alignment': None, 'sha256': 'test'}
        with patch('backend.narration.synthesize', return_value=(audio, metadata)):
            with self.assertRaisesRegex(ValueError, '120 giây'):
                prepare_narration(copy.deepcopy(script), self.root / 'output', self.root / 'cache')
            metadata['duration'] = 120
            script['phases'] = [copy.deepcopy(script['phases'][0]) for _ in range(16)]
            with self.assertRaisesRegex(ValueError, '30 phút'):
                prepare_narration(script, self.root / 'output', self.root / 'cache')

    def source_script(self):
        script = screenplay()
        script['phases'][0]['voiceover'] = 'Mây bay.'
        source = self.root / 'source.json'
        source.write_text(json.dumps(script, ensure_ascii=False), encoding='utf-8')
        return source

    def test_cli_generates_wav_and_synced_script_without_calling_text_ai(self):
        source = self.source_script()
        original = source.read_bytes()
        output = self.root / 'output'
        cache = self.root / 'cache'
        with self.engine() as engine, patch('plant_kurzge.request_text') as text_ai, \
                patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
            main(['--input', str(source), '--output', str(output), '--cache', str(cache)])
            main(['--input', str(source), '--output', str(output), '--cache', str(cache), '--overwrite'])
            engine.return_value.infer.assert_called_once()
            text_ai.assert_not_called()
        saved = json.loads((output / 'kich_ban.json').read_text(encoding='utf-8'))
        self.assertAlmostEqual(saved['total_duration'], math.ceil(1.71 * 30) / 30)
        self.assertTrue((output / saved['phases'][0]['audio']['src']).is_file())
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse((output / 'kich_ban.tmp').exists())

    def test_cli_rejects_invalid_or_unvoiced_script_before_loading_model(self):
        source = self.source_script()
        output = self.root / 'output'
        with self.engine() as factory:
            for invalid in ({}, [], {'phases': []}):
                source.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(ValueError, 'không hợp lệ'):
                    generate_audio(source, output, self.root / 'cache')
            for voiceover in (None, '', '   '):
                script = screenplay()
                script['phases'][0]['voiceover'] = voiceover
                source.write_text(json.dumps(script))
                with self.assertRaisesRegex(ValueError, 'chưa có voiceover'):
                    generate_audio(source, output, self.root / 'cache')
            factory.assert_not_called()
        self.assertFalse(output.exists())

    def test_cli_preserves_source_and_existing_output(self):
        source = self.source_script().rename(self.root / 'kich_ban.json')
        original = source.read_bytes()
        output = self.root / 'output'
        output.mkdir()
        existing = output / 'kich_ban.json'
        existing.write_text('existing result')
        with self.engine() as factory:
            for overwrite in (False, True):
                with self.assertRaisesRegex(ValueError, 'giữ nguyên'):
                    generate_audio(source, self.root, self.root / 'cache', overwrite=overwrite)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                generate_audio(source, output, self.root / 'cache')
            factory.assert_not_called()
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(existing.read_text(), 'existing result')

    def test_cli_does_not_publish_script_when_tts_fails(self):
        source = self.source_script()
        output = self.root / 'output'
        with self.engine() as factory:
            factory.return_value.infer.side_effect = RuntimeError('model failed')
            with self.assertRaisesRegex(ValueError, 'VIENEU_VOICE'):
                generate_audio(source, output, self.root / 'cache')
        self.assertFalse((output / 'kich_ban.json').exists())


if __name__ == '__main__':
    unittest.main()
