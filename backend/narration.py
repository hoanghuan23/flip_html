"""Local VieNeu TTS, immutable WAV cache and measured scene timing."""
from functools import lru_cache
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave


def probe_audio(path):
    if Path(path).suffix.lower() == '.wav':
        try:
            with wave.open(str(path), 'rb') as source:
                if source.getnchannels() < 1 or source.getframerate() < 1 or source.getnframes() < 1:
                    raise ValueError()
                return source.getnframes() / source.getframerate()
        except (OSError, wave.Error, ValueError):
            pass
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
    try:
        engine_version = version('vieneu')
    except PackageNotFoundError:
        raise ValueError('Chưa cài VieNeu trên máy chủ. Chạy python3 -m pip install -r requirements.txt.') from None
    return {'provider': 'vieneu', 'version': engine_version,
            'voice': os.getenv('VIENEU_VOICE', '').strip() or 'Hải Đăng', 'format': 'wav'}


@lru_cache(maxsize=1)
def get_tts():
    """Load the default model once per graphics worker, shared by all its scenes."""
    try:
        from vieneu import Vieneu
        return Vieneu()
    except ImportError as error:
        raise ValueError('Thiếu thư viện VieNeu. Chạy python3 -m pip install -r requirements.txt.') from error
    except Exception as error:
        raise ValueError('Không khởi tạo được VieNeu. Hãy kiểm tra model và cấu hình máy chủ.') from error


def synthesize(text, cache, *, previous_text='', next_text=''):
    config = tts_config()
    # VieNeu infer() takes only this scene's text; neighboring scenes do not
    # affect the audio and therefore do not belong in the cache identity.
    identity = {'text': text, **config}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    audio, metadata = cache / f'{digest}.wav', cache / f'{digest}.json'
    if audio.exists() and metadata.exists():
        try:
            saved = json.loads(metadata.read_text())
            if saved['sha256'] != hashlib.sha256(audio.read_bytes()).hexdigest():
                raise ValueError()
            duration = probe_audio(audio)
            if (not isinstance(saved.get('duration'), (int, float)) or not math.isfinite(saved['duration'])
                    or abs(saved['duration'] - duration) > .01):
                raise ValueError('Thời lượng audio cache không khớp.')
            if saved['alignment'] is not None:
                raise ValueError('Cache VieNeu không có alignment từng ký tự.')
            return audio, saved
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            pass
    tts = get_tts()
    try:
        generated = tts.infer(text=text, voice=config['voice'])
    except Exception as error:
        raise ValueError('VieNeu không tạo được thuyết minh. Hãy kiểm tra VIENEU_VOICE và model trên máy chủ.') from error
    try:
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            path = Path(temporary) / 'audio.wav'
            tts.save(generated, str(path))
            duration = probe_audio(path)
            # VieNeu's waveform API has no word/character timestamps. Preserve
            # that absence so consumers use numeric scene timing.
            saved = {'duration': duration, 'alignment': None,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **config}
            meta = Path(temporary) / 'audio.json'
            meta.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
            path.replace(audio)
            meta.replace(metadata)
        return audio, saved
    except Exception as error:
        raise ValueError('Không lưu được audio VieNeu hợp lệ. Hãy kiểm tra model, thư mục cache và ffprobe.') from error


def cue_time(alignment, phrase):
    if not alignment or not phrase:
        return None
    text = ''.join(alignment['characters'])
    index = text.lower().find(phrase.lower())
    return alignment['character_start_times_seconds'][index] if index >= 0 else None


def synthesize_at_cues(text, cues, cache):
    """Synthesize at exact visual cue boundaries; the stitched WAV has exact cue times."""
    boundaries = sorted({text.index(cue) for cue in cues})
    starts = [0, *(index for index in boundaries if index > 0)]
    pieces = [text[start:end] for start, end in zip(starts, [*starts[1:], len(text)])]
    files = [synthesize(piece, cache)[0] for piece in pieces]
    digest = hashlib.sha256(json.dumps({'text': text, 'starts': starts, 'tts': tts_config()},
                                     ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    target = cache / f'{digest}.wav'
    if not target.exists():
        temporary = cache / f'{digest}.tmp.wav'
        with wave.open(str(temporary), 'wb') as result:
            parameters = None
            for source in files:
                with wave.open(str(source), 'rb') as part:
                    if parameters is None:
                        parameters = part.getparams()
                        result.setparams(parameters)
                    elif (part.getnchannels(), part.getsampwidth(), part.getframerate(), part.getcomptype()) != (
                            parameters.nchannels, parameters.sampwidth, parameters.framerate, parameters.comptype):
                        raise ValueError('Các đoạn thuyết minh không cùng định dạng WAV.')
                    result.writeframes(part.readframes(part.getnframes()))
        temporary.replace(target)
    elapsed = 0.0
    positions = {}
    for start, source in zip(starts, files):
        positions[start] = elapsed
        with wave.open(str(source), 'rb') as part:
            elapsed += part.getnframes() / part.getframerate()
    duration = probe_audio(target)
    saved = {'duration': duration, 'alignment': None, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
             'cue_times': {cue: positions[text.index(cue)] for cue in cues}, **tts_config()}
    return target, saved


def prepare_narration(script, output, cache, on_progress=None):
    phases = script['phases']
    for index, phase in enumerate(phases):
        if not phase.get('voiceover'):
            continue
        if on_progress:
            on_progress('narration', index, len(phases))
        events = phase.get('illustration_events', [])
        cues = [event['cue'] for event in events if event['operation'] != 'hide']
        audio, saved = (synthesize_at_cues(phase['voiceover'], cues, cache) if cues else
                        synthesize(phase['voiceover'], cache,
                                   previous_text=phases[index - 1].get('voiceover', '') if index else '',
                                   next_text=phases[index + 1].get('voiceover', '') if index + 1 < len(phases) else ''))
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
        for event in events:
            if event['operation'] == 'hide':
                event['time'] = event.get('fraction', 0) * duration
            else:
                event['time'] = saved['cue_times'][event['cue']]
        events.sort(key=lambda event: event['time'])
        phase['duration'] = duration
        phase['audio'] = {'src': target.relative_to(output).as_posix(), 'duration': saved['duration'],
                          'alignment': metadata.relative_to(output).as_posix(), 'sha256': saved['sha256']}
        if on_progress:
            on_progress('narration', index + 1, len(phases))
    script['total_duration'] = math.fsum(p['duration'] for p in phases)
    if script['total_duration'] > 1800:
        raise ValueError('Tổng thuyết minh vượt quá thời lượng hỗ trợ 30 phút.')
