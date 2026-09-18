"""Sample-exact padding, unchanged decoded content, zero tails and boundary tests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('converter', ROOT / 'src/audio_convert.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def generate(path, frames, rate, channels, codec):
    expression = '|'.join('0.1*sin(2*PI*' + str(220 + i * 110) + '*t)' for i in range(channels))
    subprocess.run([c.FFMPEG, '-v', 'error', '-f', 'lavfi', '-i',
                    f'aevalsrc={expression}:s={rate}:d={frames/rate + 0.1}',
                    '-af', 'atrim=end_sample=' + str(frames), '-c:a', codec, str(path)], check=True)


def raw(path, codec='pcm_f64le', fmt='f64le'):
    return subprocess.check_output([c.FFMPEG, '-v', 'error', '-i', str(path),
                                    '-map', '0:a:0', '-c:a', codec, '-f', fmt, '-'])


with tempfile.TemporaryDirectory(prefix='finder-audio-pad-test-') as temporary:
    root = Path(temporary)
    cases = [
        ('to30', 282 * 4800, 48000, 2, 'pcm_s24le', 30),
        ('to35', 312 * 4410, 44100, 1, 'pcm_s16le', 35),
        ('to40', 37 * 48000, 48000, 2, 'pcm_f32le', 40),
        ('before35', 35 * 48000 - 1, 48000, 2, 'pcm_s24le', 35),
        ('exact35', 35 * 48000, 48000, 2, 'pcm_s24le', 35),
        ('after35', 35 * 48000 + 1, 48000, 2, 'pcm_s24le', 40),
        ('surround', 9601, 96000, 6, 'pcm_s32le', 5),
        ('unsigned8', 8001, 32000, 1, 'pcm_u8', 5),
        ('float64', 12345, 44100, 2, 'pcm_f64le', 5),
    ]
    for name, frames, rate, channels, codec, seconds in cases:
        source = root / (name + " 한글 ' $() `x`.wav")
        generate(source, frames, rate, channels, codec)
        checksum = hashlib.sha256(source.read_bytes()).digest()
        result = c.convert(source, 'pad', {})
        original = raw(source)
        padded = raw(result['output'])
        boundary = frames * channels * 8
        assert len(original) == boundary
        assert len(padded) == seconds * rate * channels * 8
        assert padded[:boundary] == original, name + ': original audio samples changed'
        assert not any(memoryview(padded)[boundary:]), name + ': nonzero padding'
        assert result['source_frames'] == frames
        assert result['padding_frames'] == seconds * rate - frames
        assert result['duration_seconds'] == seconds
        assert hashlib.sha256(source.read_bytes()).digest() == checksum
        stream, _ = c.probe(result['output'])
        source_stream, _ = c.probe(source)
        assert stream['codec_name'] == codec
        assert c.bits_of(stream) == c.bits_of(source_stream)
        assert int(stream['sample_rate']) == rate and stream['channels'] == channels
    # Compressed inputs are counted after decoding and become 24-bit WAV.
    seed = root / 'short.wav'
    generate(seed, 44100 + 123, 44100, 2, 'pcm_s24le')
    for codec, extension in [('libmp3lame', 'mp3'), ('aac', 'm4a'), ('flac', 'flac')]:
        source = root / ('compressed.' + extension)
        subprocess.run([c.FFMPEG, '-v', 'error', '-i', str(seed), '-c:a', codec, str(source)], check=True)
        original = raw(source, 'pcm_s24le', 's24le')
        result = c.convert(source, 'pad', {})
        padded = raw(result['output'], 'pcm_s24le', 's24le')
        assert result['source_frames'] == len(original) // 6
        assert padded[:len(original)] == original
        assert not any(memoryview(padded)[len(original):])
        assert len(padded) == 5 * 44100 * 6
        assert result['bits'] == 24
    first = c.convert(seed, 'pad', {})
    second = c.convert(seed, 'pad', {})
    assert first['output'] != second['output'] and Path(first['output']).exists()
    broken = root / 'broken.wav'
    broken.write_text('not audio')
    result = subprocess.run([sys.executable, str(ROOT / 'src/audio_convert.py'), 'pad',
                             str(seed), str(broken)], capture_output=True, text=True,
                            env=dict(os.environ, FINDER_AUDIO_NONINTERACTIVE='1',
                                     FINDER_AUDIO_LOG_DIR=str(root / 'logs')))
    assert result.returncode == 1
    assert [item['status'] for item in json.loads(result.stdout)] == ['success', 'failed']
    assert not list(root.rglob('.padding-*'))
print('PASS: exact 30/35/40 seconds, one-sample boundaries, unchanged audio, zero tails, PCM formats, compressed inputs, collisions, batch failures and cleanup')
