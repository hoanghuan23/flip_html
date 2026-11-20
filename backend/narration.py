"""Server-only ElevenLabs TTS, immutable audio cache and measured scene timing."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def probe_audio(path):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                 'format=duration:stream=codec_type', '-of', 'json', str(path)],
                                check=True, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        if not math.isfinite(duration) or duration <= 0 or not any(
                s.get('codec_type') == 'audio' for s in data.get('streams', [])):
            raise ValueError()
        return duration
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        raise ValueError('File thuyết minh không hợp lệ hoặc thiếu ffprobe trên máy chủ.') from error


def tts_config():
    from plant_kurzge import load_env
    load_env()
    key, voice = os.getenv('ELEVENLABS_API_KEY'), os.getenv('ELEVENLABS_VOICE_ID')
    if not key or not voice:
        raise ValueError('Thiếu ELEVENLABS_API_KEY hoặc ELEVENLABS_VOICE_ID trên máy chủ.')
    return {'key': key, 'voice': voice, 'model': os.getenv('ELEVENLABS_MODEL_ID', 'eleven_flash_v2_5'),
            'language': 'vi', 'format': 'mp3_44100_128'}


def validate_alignment(value, duration):
    if not isinstance(value, dict):
        raise ValueError('ElevenLabs không trả mốc thời gian lời đọc.')
    chars, starts, ends = (value.get(k) for k in
                          ('characters', 'character_start_times_seconds', 'character_end_times_seconds'))
    if not isinstance(chars, list) or not chars or not isinstance(starts, list) or not isinstance(ends, list) or not len(chars) == len(starts) == len(ends):
        raise ValueError('Mốc thời gian thuyết minh không hợp lệ.')
    previous = 0
    for char, start, end in zip(chars, starts, ends):
        if (not isinstance(char, str) or not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end))
                or not 0 <= start <= end <= duration + .25 or start < previous):
            raise ValueError('Mốc thời gian thuyết minh nằm ngoài audio.')
        previous = start
    return value


def synthesize(text, cache, *, previous_text='', next_text=''):
    config = tts_config()
    identity = {'text': text, 'previous_text': previous_text, 'next_text': next_text,
                **{k: v for k, v in config.items() if k != 'key'}}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    audio, metadata = cache / f'{digest}.mp3', cache / f'{digest}.json'
    if audio.exists() and metadata.exists():
        try:
            saved = json.loads(metadata.read_text())
            if saved['sha256'] != hashlib.sha256(audio.read_bytes()).hexdigest():
                raise ValueError()
            duration = probe_audio(audio)
            if (not isinstance(saved.get('duration'), (int, float)) or not math.isfinite(saved['duration'])
                    or abs(saved['duration'] - duration) > .01):
                raise ValueError('Thời lượng audio cache không khớp.')
            validate_alignment(saved['alignment'], duration)
            return audio, saved
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            pass
    from urllib.parse import quote
    url = ('https://api.elevenlabs.io/v1/text-to-speech/' + quote(config['voice'], safe='')
           + '/with-timestamps?output_format=' + config['format'])
    body = {'text': text, 'model_id': config['model'], 'language_code': config['language'],
            'previous_text': previous_text[-1000:] or None, 'next_text': next_text[:1000] or None}
    request = Request(url, data=json.dumps(body).encode(), method='POST',
                      headers={'xi-api-key': config['key'], 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=180) as response:
            data = json.load(response)
    except HTTPError as error:
        messages = {401: 'Khóa ElevenLabs không hợp lệ.', 403: 'ElevenLabs từ chối quyền truy cập giọng đọc.',
                    429: 'ElevenLabs hết hạn mức hoặc đang giới hạn yêu cầu. Hãy thử lại sau.'}
        try:
            detail = json.loads(error.read(4096)).get('detail', {})
            status = detail.get('status') if isinstance(detail, dict) else None
            if not isinstance(status, str):
                status = None
        except (ValueError, OSError, AttributeError):
            status = None
        statuses = {'quota_exceeded': 'ElevenLabs không còn đủ hạn mức để tạo thuyết minh.',
                    'invalid_api_key': messages[401],
                    'voice_not_found': 'Không tìm thấy ELEVENLABS_VOICE_ID đã cấu hình.',
                    'max_character_limit_exceeded': 'Lời đọc vượt giới hạn ký tự của model ElevenLabs.'}
        raise ValueError(statuses.get(status, messages.get(error.code,
                         f'ElevenLabs trả HTTP {error.code}. Hãy thử tạo lại đồ họa.'))) from None
    except (URLError, TimeoutError):
        raise ValueError('Không kết nối được ElevenLabs hoặc quá thời gian chờ. Hãy thử lại.') from None
    except (ValueError, UnicodeError):
        raise ValueError('ElevenLabs trả phản hồi JSON không hợp lệ.') from None
    try:
        raw = base64.b64decode(data['audio_base64'], validate=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            path = Path(temporary) / 'audio.mp3'
            path.write_bytes(raw)
            duration = probe_audio(path)
            alignment = validate_alignment(data.get('alignment'), duration)
            saved = {'duration': duration, 'alignment': alignment, 'sha256': hashlib.sha256(raw).hexdigest(),
                     'model': config['model']}
            meta = Path(temporary) / 'audio.json'
            meta.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
            path.replace(audio)
            meta.replace(metadata)
        return audio, saved
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('ElevenLabs trả audio hoặc mốc thời gian không hợp lệ.') from error


def cue_time(alignment, phrase):
    if not phrase:
        return None
    text = ''.join(alignment['characters'])
    index = text.lower().find(phrase.lower())
    return alignment['character_start_times_seconds'][index] if index >= 0 else None


def prepare_narration(script, output, cache, on_progress=None):
    phases = script['phases']
    for index, phase in enumerate(phases):
        if not phase.get('voiceover'):
            continue
        if on_progress:
            on_progress('narration', index, len(phases))
        audio, saved = synthesize(phase['voiceover'], cache,
                                 previous_text=phases[index - 1].get('voiceover', '') if index else '',
                                 next_text=phases[index + 1].get('voiceover', '') if index + 1 < len(phases) else '')
        duration = math.ceil(saved['duration'] * 30) / 30
        if duration > 120:
            raise ValueError(f"Lời đọc cảnh {index + 1} dài hơn 120 giây. Hãy chia thành các cảnh ngắn hơn.")
        directory = output / 'assets' / 'audio'
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / audio.name
        shutil.copy2(audio, target)
        metadata = target.with_suffix('.json')
        metadata.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
        old = phase['duration']
        for action in phase['actions']:
            start = cue_time(saved['alignment'], action.get('cue'))
            action['start'] = start if start is not None else action['start'] / old * duration
            action['end'] = min(duration, max(action['start'] + 1 / 30, action['end'] / old * duration))
        phase['duration'] = duration
        phase['audio'] = {'src': target.relative_to(output).as_posix(), 'duration': saved['duration'],
                          'alignment': metadata.relative_to(output).as_posix(), 'sha256': saved['sha256']}
        if on_progress:
            on_progress('narration', index + 1, len(phases))
    script['total_duration'] = math.fsum(p['duration'] for p in phases)
    if script['total_duration'] > 1800:
        raise ValueError('Tổng thuyết minh vượt quá thời lượng hỗ trợ 30 phút.')
