"""Contract tests for the shared text-only web/CLI analysis pipeline."""
import contextlib
import copy
import io
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from fastapi.testclient import TestClient

import plant_kurzge as planner
from backend.script_worker import run as run_worker
from backend.app import create_app
from backend.scripts import project_script
from backend.test_scripts import screenplay
from script_analysis import parse_detailed, speech_seconds


DETAIL = '''# Vệ tinh
## **Phase 1: Giới thiệu**
**Hoạt ảnh:** Vệ tinh chuyển động phía trên Trái Đất.
**Audio:** Độ cao 550 km.
Câu lặp lại.

### Cảnh 2 – So sánh
Mô tả: Trái Đất hiện ra và số liệu được gắn bên cạnh vệ tinh.
Lời đọc: Câu lặp lại.
Độ cao 550 km.
'''


def classification(kind='topic', **extra):
    return json.dumps({'valid': True, 'reason': '', 'topic': 'Vệ tinh', 'input_type': kind,
                       'image_dependent': False, **extra}, ensure_ascii=False)


def generated(kind='topic', text=DETAIL):
    script = screenplay()
    sources = parse_detailed(text) if kind == 'detailed_script' else []
    base = script['phases'][0]
    script['phases'] = []
    for i, source in enumerate(sources or [{'name': 'Mưa đá', 'voiceover': 'Nước đóng băng trong mây.'}], 1):
        phase = copy.deepcopy(base)
        phase.update(id=i, name=source['name'] or f'Ý {i}', voiceover=source['voiceover'],
                     annotations=[{'text': 'Độ cao', 'target': 'CLOUD', 'action_index': 0,
                                   'cue': source['voiceover'].splitlines()[0]}], duration_status='estimated')
        script['phases'].append(phase)
    script['total_duration'] = sum(p['duration'] for p in script['phases'])
    script['warnings'] = ['Phase 2: kiểm tra lại số liệu.'] if sources else []
    return script


def research(status='sources_reported', **extra):
    return json.dumps({'sufficient': True, 'reason': '', 'summary': 'Nước đóng băng trong mây.',
                       'status': status, 'sources': ([{'title': 'Nguồn gốc', 'url': 'https://example.org/hail',
                                                     'claims': ['Nước đóng băng trong mây.']}] if status == 'sources_reported' else []),
                       **extra}, ensure_ascii=False)


class DetailedTests(unittest.TestCase):
    def test_markdown_aliases_and_source_audio_keep_internal_whitespace(self):
        source = parse_detailed(DETAIL)
        self.assertEqual([s['name'] for s in source], ['Giới thiệu', 'So sánh'])
        self.assertEqual(source[0]['voiceover'], 'Độ cao 550 km.\nCâu lặp lại.')
        self.assertEqual(source[1]['voiceover'], 'Câu lặp lại.\nĐộ cao 550 km.')
        for heading, visual, voice in [('Phần 7: Tên', 'Mô tả', 'Thuyết minh'),
                                       ('**Cảnh 2 – Tên**', 'Hoạt ảnh', 'Audio'),
                                       ('### **Phase 1**: Tên', '- **Hoạt ảnh**', '- **Audio**')]:
            phase = parse_detailed(f'{heading}\n{visual}: A\n{voice}: B')[0]
            self.assertEqual(phase['voiceover'], 'B')
            self.assertEqual(phase['name'], 'Tên')

    def test_hybrid_empty_and_ambiguous_sections_rejected_before_generation(self):
        for text in ['Phase 1: A\nMô tả: X', 'Cảnh 1: A\nAudio: X',
                     'Phần 1: A\nMô tả: X\nAudio:',
                     'Phase 1: A\nMô tả: X\nAudio: Y\nThuyết minh: Z']:
            with self.subTest(text=text), patch.object(planner, 'request_text') as call:
                with self.assertRaises(planner.InputRejectedError):
                    planner.generate_script(text)
                call.assert_not_called()

    def test_phase_count_title_audio_and_repeated_sentences_survive_repairs(self):
        correct = generated('detailed_script')
        variants = []
        changed = copy.deepcopy(correct); changed['phases'].reverse(); variants.append(changed)
        changed = copy.deepcopy(correct); changed['phases'].pop(); variants.append(changed)
        changed = copy.deepcopy(correct); changed['phases'][0]['name'] = 'Đổi tên'; variants.append(changed)
        for broken in variants:
            with self.subTest(broken=broken), patch.object(planner, 'request_text', side_effect=[
                    classification('legacy'), json.dumps(broken), json.dumps(correct)]) as call:
                result = planner.generate_script(DETAIL)
                self.assertEqual(result['input_type'], 'detailed_script')
                for phase, source in zip(result['phases'], parse_detailed(DETAIL)):
                    self.assertEqual(phase['voiceover'], source['voiceover'])
                    self.assertEqual(phase['source'], source)
                self.assertEqual(call.call_count, 3)

    def test_source_audio_is_restored_without_requiring_an_exact_model_copy(self):
        for speech in ['Độ cao 550 km! Câu lặp lại…', 'Độ cao 600 km.', '', None]:
            raw = generated('detailed_script')
            if speech is None:
                del raw['phases'][0]['voiceover']
            else:
                raw['phases'][0]['voiceover'] = speech
            with self.subTest(speech=speech), patch.object(planner, 'request_text', side_effect=[
                    classification('detailed_script'), json.dumps(raw)]) as call:
                result = planner.generate_script(DETAIL)
                self.assertEqual(call.call_count, 2)
                for phase, source in zip(result['phases'], parse_detailed(DETAIL)):
                    self.assertEqual(phase['voiceover'], source['voiceover'])
                    self.assertEqual(phase['source'], source)
                self.assertEqual(planner.validate_generated(result), [])

    def test_long_phase_is_rejected_without_splitting(self):
        text = 'Phase 1: Dài\nHoạt ảnh: A\nAudio: ' + 'chữ ' * 500
        with patch.object(planner, 'request_text') as call, self.assertRaisesRegex(planner.InputRejectedError, 'Phase 1'):
            planner.generate_script(text)
        call.assert_not_called()

    def test_audio_over_1000_characters_can_stay_in_one_phase(self):
        text = 'Phase 1: A\nHoạt ảnh: Mây chuyển động.\nAudio: ' + 'abcdefghij ' * 100
        with patch.object(planner, 'request_text', side_effect=[classification('detailed_script'), json.dumps(generated('detailed_script', text))]):
            script = planner.generate_script(text)
        self.assertEqual(len(script['phases']), 1)
        self.assertGreater(len(script['phases'][0]['voiceover']), 1000)


class TopicTests(unittest.TestCase):
    def test_research_is_separate_and_sources_are_not_independent_verification(self):
        stages = []
        with patch.object(planner, 'request_text', side_effect=[classification(), research(), json.dumps(generated())]) as call:
            script = planner.generate_script('Mưa đá hình thành như thế nào?', on_stage=stages.append)
        self.assertEqual(script['research']['status'], 'sources_reported')
        self.assertEqual(script['input_type'], 'topic')
        self.assertIn('researching', stages)
        self.assertIn('normalizing', stages)
        self.assertIn('Nghiên cứu chủ đề', call.call_args_list[1].args[0])
        self.assertIn('https://example.org/hail', call.call_args_list[2].args[0])
        self.assertEqual(project_script(script)['research'], script['research'])

    def test_unavailable_search_produces_explicit_unverified_draft(self):
        for unavailable in [research('unverified'), URLError('offline')]:
            with self.subTest(unavailable=unavailable), patch.object(planner, 'request_text', side_effect=[classification(), unavailable, json.dumps(generated())]):
                script = planner.generate_script('Mưa đá hình thành như thế nào?')
            self.assertEqual(script['research']['sources'], [])
            self.assertEqual(script['research']['status'], 'unverified')
            self.assertTrue(any('chưa được kiểm chứng' in w for w in script['warnings']))

    def test_insufficient_research_or_image_dependent_input_rejected(self):
        with patch.object(planner, 'request_text', side_effect=[classification(), research(sufficient=False, reason='Thiếu sự kiện cụ thể.')]) as call:
            with self.assertRaisesRegex(planner.InputRejectedError, 'sự kiện'):
                planner.generate_script('Chủ đề chưa rõ')
            self.assertEqual(call.call_count, 2)
        with patch.object(planner, 'request_text', return_value=classification(image_dependent=True)) as call:
            with self.assertRaisesRegex(planner.InputRejectedError, 'mô tả bằng văn bản'):
                planner.generate_script('Làm theo ảnh này')
            call.assert_called_once()

    def test_unsafe_or_inconsistent_research_sources_are_rejected(self):
        for sources in [[{'title': 'X', 'url': 'javascript:alert(1)', 'claims': ['X']}], []]:
            with patch.object(planner, 'request_text', side_effect=[classification(), research(sources=sources)]):
                with self.assertRaises(ValueError):
                    planner.generate_script('Mưa đá')


class NormalizationTests(unittest.TestCase):
    def test_duration_status_is_set_before_validation_without_ai_repairs(self):
        detailed = '\n\n'.join(
            f'Phase {i}: Ý {i}\nHoạt ảnh: Mây chuyển động.\nAudio: Lời đọc cho cảnh {i}.'
            for i in range(1, 6))
        for kind in ('topic', 'detailed_script'):
            for status in (None, 'final', 'Estimated', '', 42):
                raw = generated(kind, detailed)
                for phase in raw['phases']:
                    if status is None:
                        phase.pop('duration_status')
                    else:
                        phase['duration_status'] = status
                replies = [classification(kind)]
                if kind == 'topic':
                    replies.append(research())
                replies.append(json.dumps(raw))
                content = detailed if kind == 'detailed_script' else 'Mưa đá hình thành như thế nào?'
                with self.subTest(kind=kind, status=status), patch.object(
                        planner, 'request_text', side_effect=replies) as call:
                    result = planner.generate_script(content)
                    self.assertEqual(call.call_count, len(replies))
                    self.assertEqual(len(result['phases']), len(raw['phases']))
                    self.assertTrue(all(p['duration_status'] == 'estimated' for p in result['phases']))
                    self.assertTrue(all(p['duration_status'] == 'estimated'
                                        for p in project_script(result)['scenes']))
                    self.assertEqual(planner.validate_generated(result), [])

    def test_invalid_annotation_mapping_is_repaired(self):
        for delta in [{'target': 'missing'}, {'action_index': 99}, {'action_index': True}, {'text': ''}]:
            correct = generated('detailed_script')
            broken = copy.deepcopy(correct)
            broken['phases'][0]['annotations'][0].update(delta)
            with patch.object(planner, 'request_text', side_effect=[classification('detailed_script'), json.dumps(broken), json.dumps(correct)]) as call:
                result = planner.generate_script(DETAIL)
                self.assertEqual(call.call_count, 3)
                self.assertEqual(planner.validate_generated(result), [])

    def test_unmatched_optional_cues_do_not_block_generation(self):
        for cue in ['không có', 'Độ cao 550 km!', '', None, 42]:
            raw = generated('detailed_script')
            phase = raw['phases'][0]
            phase['annotations'][0]['cue'] = cue
            phase['actions'][0]['cue'] = cue
            action = copy.deepcopy(phase['actions'][0])
            with self.subTest(cue=cue), patch.object(planner, 'request_text', side_effect=[
                    classification('detailed_script'), json.dumps(raw)]) as call:
                result = planner.generate_script(DETAIL)
                self.assertEqual(call.call_count, 2)
                phase = result['phases'][0]
                self.assertNotIn('cue', phase['annotations'][0])
                self.assertNotIn('cue', phase['actions'][0])
                self.assertEqual(phase['actions'][0], {k: v for k, v in action.items() if k != 'cue'})
                self.assertEqual(phase['voiceover'], parse_detailed(DETAIL)[0]['voiceover'])
                self.assertEqual(result['phases'][1]['annotations'][0]['cue'], 'Câu lặp lại.')
                self.assertEqual(planner.validate_generated(result), [])
                self.assertTrue(project_script(result)['scenes'][0]['annotations'])

    def test_optional_cues_restore_source_case_and_whitespace(self):
        raw = generated('detailed_script')
        raw['phases'][0]['annotations'][0]['cue'] = 'độ   cao 550 km. câu lặp lại.'
        with patch.object(planner, 'request_text', side_effect=[
                classification('detailed_script'), json.dumps(raw)]) as call:
            result = planner.generate_script(DETAIL)
        self.assertEqual(call.call_count, 2)
        phase = result['phases'][0]
        self.assertEqual(phase['annotations'][0]['cue'], phase['voiceover'])
        self.assertEqual(planner.validate_generated(result), [])

    def test_timing_takes_maximum_and_keeps_actions_valid(self):
        raw = generated('detailed_script')
        raw['phases'][0]['duration'] = 1
        raw['phases'][0]['actions'][0]['end'] = 1
        raw['total_duration'] = sum(p['duration'] for p in raw['phases'])
        with patch.object(planner, 'request_text', side_effect=[classification('detailed_script'), json.dumps(raw)]):
            result = planner.generate_script(DETAIL)
        p = result['phases'][0]
        self.assertGreaterEqual(p['duration'], speech_seconds(p['voiceover']))
        self.assertEqual(result['phases'][1]['duration'], 7.25)
        self.assertAlmostEqual(sum(p['duration'] for p in result['phases']), result['total_duration'])
        with patch.dict('os.environ', {'SCRIPT_SPEECH_UNITS_PER_MINUTE': '120'}):
            self.assertEqual(speech_seconds('một hai'), 1)

    def test_two_repairs_limit_and_empty_annotations(self):
        raw = generated('detailed_script')
        broken = copy.deepcopy(raw); broken['phases'] = []
        with patch.object(planner, 'request_text', side_effect=[classification('detailed_script')] + [json.dumps(broken)] * 3) as call:
            with self.assertRaisesRegex(ValueError, 'không đạt kiểm tra'):
                planner.generate_script(DETAIL, retries=10)
            self.assertEqual(call.call_count, 4)
        for p in raw['phases']:
            p['annotations'] = []
        with patch.object(planner, 'request_text', side_effect=[classification('detailed_script'), json.dumps(raw)]):
            self.assertEqual(planner.generate_script(DETAIL)['phases'][0]['annotations'], [])

    def test_no_image_mapping_and_audio_mentions_preserved(self):
        text = DETAIL.replace('Độ cao 550 km.', 'Hình 9 ở độ cao 550 km.')
        raw = generated('detailed_script', text)
        with patch.object(planner, 'request_text', side_effect=[classification('detailed_script'), json.dumps(raw)]):
            result = planner.generate_script(text)
        self.assertTrue(any('Chỉ dẫn ảnh' in w for w in result['warnings']))
        self.assertIn('Hình 9', result['phases'][0]['voiceover'])
        self.assertNotIn('image_refs', result['phases'][0])

    def test_cli_and_web_share_output_and_ignore_stale_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = root / 'input.txt'; content.write_text(DETAIL)
            (root / 'references.json').write_text('not even JSON: ignored')
            replies = [classification('detailed_script'), json.dumps(generated('detailed_script'))]
            with patch.multiple(planner, API_URL='test', API_KEY='test', MODEL='test'), \
                    patch.object(planner, 'request_text', side_effect=replies) as api, \
                    contextlib.redirect_stdout(io.StringIO()):
                run_worker(root)
            web = json.loads((root / 'kich_ban.json').read_text())
            self.assertNotIn('REFERENCE IMAGES', api.call_args.args[0])
            with patch.object(planner, 'request_text', side_effect=replies), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                planner.main(['--input', str(content), '--output', str(root / 'cli.json')])
            self.assertEqual(json.loads((root / 'cli.json').read_text()), web)
            projection = project_script(web)
            self.assertEqual(projection['warnings'], web['warnings'])
            self.assertEqual(projection['scenes'][0]['annotations'], web['phases'][0]['annotations'])


class AnalysisApiTests(unittest.TestCase):
    def test_real_job_process_publishes_new_metadata_for_both_branches(self):
        requests = []
        current = {'kind': 'topic'}

        class Fixture(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(payload)
                prompt = payload['prompt']
                if prompt.startswith('Đánh giá nội dung'):
                    result = classification(current['kind'])
                elif prompt.startswith(planner.RESEARCH_PROMPT):
                    result = research()
                else:
                    result = json.dumps(generated(current['kind']), ensure_ascii=False)
                response = json.dumps({'success': True, 'result': result}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary, patch.dict('os.environ', {
                    'CODEX_API_URL': f'http://127.0.0.1:{server.server_port}/generate',
                    'CODEX_API_TOKEN': 'test-only', 'CODEX_MODEL': 'fixture'}):
                root = Path(temporary)
                with TestClient(create_app(root)) as client:
                    for kind, text in [('topic', 'Mưa đá hình thành như thế nào?'), ('detailed_script', DETAIL)]:
                        current['kind'] = kind
                        response = client.post('/api/scripts', json={'projectId': kind, 'content': text})
                        self.assertEqual(response.status_code, 202)
                        job = response.json()
                        deadline = time.monotonic() + 10
                        while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
                            time.sleep(.02)
                            job = client.get('/api/scripts/' + job['id']).json()
                        self.assertEqual(job['status'], 'succeeded', job)
                        result = job['result']
                        self.assertEqual(result['input_type'], kind)
                        self.assertEqual(result['scenes'][0]['duration_status'], 'estimated')
                        self.assertTrue(result['scenes'][0]['annotations'])
                        directory = root / 'scripts' / job['id']
                        self.assertFalse((directory / 'references.json').exists())
                        canonical = json.loads((directory / 'kich_ban.json').read_text())
                        self.assertEqual(result, project_script(canonical))
                        if kind == 'topic':
                            self.assertEqual(result['research']['status'], 'sources_reported')
                        else:
                            self.assertEqual([s['voiceover'] for s in result['scenes']],
                                             [s['voiceover'] for s in parse_detailed(DETAIL)])
                for payload in requests:
                    self.assertEqual(set(payload), {'prompt', 'model'})
                    self.assertNotIn('data:image/', payload['prompt'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
