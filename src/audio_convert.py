#!/usr/bin/python3
"""Finder audio Quick Actions. Originals are never modified."""
import argparse
import datetime
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile

def find_tool(name):
    config_path = Path(__file__).parent / 'config.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    candidates = [os.environ.get('FINDER_AUDIO_' + name.upper()), config.get(name),
                  shutil.which(name), '/opt/homebrew/bin/' + name, '/usr/local/bin/' + name]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).absolute())
    return name


FFMPEG = find_tool('ffmpeg')
FFPROBE = find_tool('ffprobe')
TITLE = 'Finder Audio Converter'


class Cancelled(Exception):
    pass


def run_dialog(mode, message=''):
    executable = Path(__file__).parent / 'Finder Audio Converter.app/Contents/MacOS/AudioDialog'
    process = subprocess.run([str(executable), mode, message], text=True, capture_output=True)
    if process.returncode == 2:
        raise Cancelled()
    if process.returncode:
        raise RuntimeError('Could not open the settings window: ' + process.stderr.strip())
    return process.stdout.strip()


def dialog(message):
    run_dialog('message', message)


def probe(path):
    p = subprocess.run([FFPROBE, '-v', 'error', '-select_streams', 'a', '-show_streams',
                        '-show_format', '-of', 'json', str(path)], text=True, capture_output=True)
    if p.returncode:
        raise ValueError('Could not read audio information: ' + p.stderr.strip()[-400:])
    data = json.loads(p.stdout)
    if len(data.get('streams', [])) != 1:
        raise ValueError('Only files with exactly one audio stream are supported.')
    return data['streams'][0], data.get('format', {})


def bits_of(stream):
    return int(stream.get('bits_per_raw_sample') or stream.get('bits_per_sample') or 0)


def source_format(path, stream):
    codec = stream['codec_name']
    suffix = path.suffix.lower()
    if suffix in ('.wav', '.wave') and codec.startswith('pcm_'):
        return 'wav'
    if suffix in ('.aif', '.aiff', '.aifc') and codec.startswith('pcm_'):
        return 'aiff'
    return {'flac': 'flac', 'alac': 'alac', 'aac': 'aac', 'mp3': 'mp3',
            'opus': 'opus', 'vorbis': 'vorbis'}.get(codec)


def custom_settings():
    return json.loads(run_dialog('settings'))


def plan(path, mode, settings):
    s, container = probe(path)
    if mode == 'mono' and s['channels'] == 1:
        return None
    fmt = 'mp3' if mode == 'mp3' else (source_format(path, s) if mode == 'mono' else settings['format'])
    if not fmt:
        raise ValueError('This source format cannot be preserved automatically. Choose an output format such as WAV in Custom Settings.')
    rate = settings.get('rate', 0) or int(s['sample_rate'])
    channel_mode = 'mono' if mode == 'mono' else settings.get('channels', 'keep')
    channels = s['channels'] if channel_mode == 'keep' else (2 if channel_mode == 'stereo' else 1)
    filters = []
    if channel_mode in ('left', 'right'):
        if s['channels'] != 2:
            raise ValueError('Left/right channel extraction requires a 2-channel stereo source.')
        filters.append('pan=mono|c0=c' + ('0' if channel_mode == 'left' else '1'))
    elif channel_mode == 'mono' and s['channels'] == 2:
        filters.append('pan=mono|c0=0.5*c0+0.5*c1')
    bitrate = 256 if mode == 'mp3' else settings.get('bitrate', round(int(s.get('bit_rate') or container.get('bit_rate') or 256000) / 1000))
    args = []
    expected_bits = None
    if fmt in ('wav', 'aiff', 'flac', 'alac'):
        depth = settings.get('depth', 'keep')
        original_bits = bits_of(s)
        if depth == 'keep':
            is_float = s['codec_name'].startswith('pcm_f')
            depth = ('float' + str(original_bits)) if is_float else str(original_bits or 24)
        if mode == 'mono' and fmt in ('wav', 'aiff'):
            codec = s['codec_name']
            expected_bits = original_bits
        elif fmt in ('wav', 'aiff'):
            endian = 'le' if fmt == 'wav' else 'be'
            if depth.startswith('float'):
                codec = 'pcm_f' + depth[5:] + endian
                expected_bits = int(depth[5:])
            elif depth in ('16', '24', '32'):
                codec = 'pcm_s' + depth + endian
                expected_bits = int(depth)
            elif depth == '8':
                codec = 'pcm_u8' if fmt == 'wav' else 'pcm_s8'
                expected_bits = 8
            else:
                raise ValueError('Unsupported bit depth. Choose 16 or 24 bit.')
        else:
            if depth not in ('16', '24'):
                raise ValueError('This lossless format supports 16 or 24 bit in this tool. Select a bit depth in Custom Settings.')
            expected_bits = int(depth)
            codec = fmt
            args += ['-sample_fmt', ('s16' if depth == '16' else 's32') + ('p' if fmt == 'alac' else '')]
            args += ['-bits_per_raw_sample', depth]
            if fmt == 'flac':
                args += ['-compression_level', '8']
        args += ['-c:a', codec]
        if expected_bits and original_bits > expected_bits:
            filters.append('aresample=dither_method=triangular')
    elif fmt == 'mp3':
        if channels not in (1, 2):
            raise ValueError('MP3 supports mono or stereo only. Select downmix in Custom Settings.')
        if mode == 'mono':
            allowed = [32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320] if rate >= 32000 else [8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
            bitrate = min(allowed, key=lambda b: abs(b-bitrate))
        if rate not in (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000):
            raise ValueError('MP3 does not support the source sample rate. Choose a supported rate, such as 44.1 or 48 kHz, in Custom Settings.')
        if rate < 32000 and bitrate > 160:
            raise ValueError('MP3 at 256/320 kbps is not supported at this sample rate. In Custom Settings, choose 32, 44.1 or 48 kHz, or a lower bitrate.')
        args += ['-c:a', 'libmp3lame', '-b:a', str(bitrate) + 'k', '-compression_level', '0']
    elif fmt == 'aac':
        args += ['-c:a', 'aac', '-b:a', str(bitrate) + 'k', '-movflags', '+faststart']
    elif fmt == 'opus':
        args += ['-c:a', 'libopus', '-b:a', str(bitrate) + 'k']
    elif fmt == 'vorbis':
        args += ['-c:a', 'libvorbis', '-q:a', '6']
    args += ['-ar', str(rate), '-ac', str(channels)]
    if filters:
        args += ['-af', ','.join(filters)]
    suffix = {'wav': '.wav', 'aiff': '.aiff', 'flac': '.flac', 'mp3': '.mp3',
              'aac': '.m4a', 'alac': '.m4a', 'opus': '.opus', 'vorbis': '.ogg'}[fmt]
    label = 'mono' if mode == 'mono' else ('256k' if mode == 'mp3' else str(rate) + 'Hz_' +
            (str(expected_bits) + 'bit_' if expected_bits else str(bitrate) + 'k_') + str(channels) + 'ch')
    return {'args': args, 'rate': rate, 'channels': channels, 'bits': expected_bits,
            'bitrate': bitrate if fmt == 'mp3' else None, 'suffix': suffix, 'label': label, 'format': fmt}


def publish_output(temp, destination, base, suffix):
    count = 1
    while True:
        target = destination / (base + ('' if count == 1 else '_' + str(count)) + suffix)
        try:
            os.link(temp, target)
            return target
        except FileExistsError:
            count += 1


def pcm_frame_count(stream):
    """Use the decoded WAV's integer time base, never rounded duration seconds."""
    frames = int(stream['duration_ts']) * Fraction(stream['time_base']) * int(stream['sample_rate'])
    if frames.denominator != 1 or frames <= 0:
        raise ValueError('Could not determine the exact decoded audio sample count.')
    return int(frames)


def pad_to_five_seconds(path):
    # Decode once before counting: lossy container duration can include encoder padding.
    p = plan(path, 'custom', {'format': 'wav', 'channels': 'keep', 'depth': 'keep'})
    destination = path.parent / 'Converted'
    destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.padding-', dir=str(destination)) as temporary:
        decoded = Path(temporary) / 'decoded.wav'
        command = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                   '-i', str(path), '-map', '0:a:0', '-map_metadata', '0', '-vn']
        process = subprocess.run(command + p['args'] + ['-rf64', 'auto', str(decoded)],
                                 text=True, capture_output=True)
        if process.returncode:
            raise ValueError(process.stderr.strip()[-700:])
        original, _ = probe(decoded)
        frames = pcm_frame_count(original)
        interval = p['rate'] * 5
        target_frames = ((frames + interval - 1) // interval) * interval
        seconds = target_frames // p['rate']
        output_path = decoded
        if target_frames > frames:
            output_path = Path(temporary) / 'padded.wav'
            process = subprocess.run([
                FFMPEG, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                '-i', str(decoded), '-map', '0:a:0', '-map_metadata', '0',
                '-c:a', original['codec_name'], '-af', 'apad=whole_len=' + str(target_frames),
                '-rf64', 'auto', str(output_path)], text=True, capture_output=True)
            if process.returncode:
                raise ValueError(process.stderr.strip()[-700:])
        output, _ = probe(output_path)
        if (pcm_frame_count(output) != target_frames or int(output['sample_rate']) != p['rate']
                or output['channels'] != p['channels'] or bits_of(output) != p['bits']):
            raise ValueError('Padded WAV sample count or audio format verification failed.')
        target = publish_output(output_path, destination, path.stem + '_padded_' + str(seconds) + 's', '.wav')
        return {'source': str(path), 'status': 'success', 'output': str(target),
                'sample_rate': p['rate'], 'channels': p['channels'], 'bits': p['bits'], 'format': 'wav',
                'duration_seconds': seconds, 'source_frames': frames,
                'output_frames': target_frames, 'padding_frames': target_frames - frames}


def convert(path, mode, settings):
    path = Path(path).absolute()
    if not path.is_file():
        raise ValueError('Select regular audio files only.')
    if mode == 'pad':
        return pad_to_five_seconds(path)
    p = plan(path, mode, settings)
    if p is None:
        return {'source': str(path), 'status': 'skipped', 'reason': 'Already mono.'}
    destination = path.parent / 'Converted'
    destination.mkdir(exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.converting-', suffix=p['suffix'], dir=str(destination))
    os.close(fd)
    try:
        command = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-i', str(path),
                   '-map', '0:a:0', '-map_metadata', '0', '-vn'] + p['args'] + [temp]
        process = subprocess.run(command, text=True, capture_output=True)
        if process.returncode:
            raise ValueError(process.stderr.strip()[-700:])
        output, _ = probe(temp)
        if int(output['sample_rate']) != p['rate'] or output['channels'] != p['channels']:
            raise ValueError('Output sample rate or channel verification failed.')
        if p['bits'] and bits_of(output) != p['bits']:
            raise ValueError('Output bit depth verification failed.')
        if p['bitrate'] and int(output.get('bit_rate') or 0) != p['bitrate'] * 1000:
            raise ValueError('Output MP3 bitrate verification failed.')
        base = path.stem + '_' + p['label']
        target = publish_output(temp, destination, base, p['suffix'])
        return {'source': str(path), 'status': 'success', 'output': str(target),
                'sample_rate': p['rate'], 'channels': p['channels'], 'bits': p['bits'], 'format': p['format']}
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['mono', 'mp3', 'custom', 'pad'])
    parser.add_argument('--settings-json', help='Custom settings as JSON; use with headless mode.')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()
    quiet = os.environ.get('FINDER_AUDIO_NONINTERACTIVE') == '1'
    try:
        if not Path(FFMPEG).is_file() or not Path(FFPROBE).is_file():
            raise ValueError('FFmpeg or ffprobe was not found.')
        if args.mode == 'custom':
            if args.settings_json:
                settings = json.loads(args.settings_json)
            elif quiet:
                raise ValueError('Headless custom mode requires --settings-json.')
            else:
                settings = custom_settings()
        else:
            settings = {}
        results = []
        for filename in args.files:
            try:
                results.append(convert(filename, args.mode, settings))
            except Exception as exc:
                results.append({'source': filename, 'status': 'failed', 'reason': str(exc)})
        log_dir = Path(os.environ.get('FINDER_AUDIO_LOG_DIR', str(Path.home() / 'Library/Logs/Finder Audio Converter')))
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        report = log_dir / (stamp + '.json')
        report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        counts = {status: sum(r['status'] == status for r in results) for status in ('success', 'skipped', 'failed')}
        message = 'Completed: {success} · Skipped: {skipped} · Failed: {failed}'.format(**counts)
        message += '\nOutput: Converted folder next to each source file\nOriginal files are unchanged.'
        for result in [r for r in results if r['status'] != 'success'][:6]:
            message += '\n\n' + Path(result['source']).name + '\n' + result['reason']
        if counts['failed'] or counts['skipped']:
            message += '\n\nDetails: ' + str(report)
        if quiet:
            print(json.dumps(results, ensure_ascii=False))
        else:
            dialog(message)
        return 1 if quiet and counts['failed'] else 0
    except Cancelled:
        return 0
    except Exception as exc:
        if quiet:
            print(str(exc), file=sys.stderr)
        else:
            dialog(str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
