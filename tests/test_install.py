"""Isolated build/install, upgrade, workflow execution and uninstall smoke test."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='finder-audio-install-') as temporary:
    base = Path(temporary) / "space ' 한국어 $() `quote`"
    runtime, services = base / 'Runtime', base / 'Services'
    services.mkdir(parents=True)
    sentinel = services / 'Unrelated.workflow'
    sentinel.write_text('keep me')
    args = [sys.executable, str(ROOT / 'scripts/install.py'), '--prefix', str(runtime),
            '--services-dir', str(services), '--skip-register']
    subprocess.run(args, check=True)
    # Only the installer needs the source checkout; installed conversions are standalone.
    source = base / "source ' 한글 $() `quote`.wav"
    config = json.loads((runtime / 'config.json').read_text())
    subprocess.run([config['ffmpeg'], '-v', 'error', '-f', 'lavfi', '-i',
                    'aevalsrc=0.1*sin(2*PI*440*t)|0.1*sin(2*PI*880*t):s=48000:d=0.2',
                    '-c:a', 'pcm_s24le', str(source)], check=True)
    for name, mode in [('Downmix to Mono', 'mono'), ('MP3 256 kbps', 'mp3'), ('Custom Settings…', 'custom')]:
        workflow = services / (name + '.workflow') / 'Contents'
        info = plistlib.loads((workflow / 'Info.plist').read_bytes())
        assert info['NSServices'][0]['NSIconName'] == 'NSTouchBarAudioOutputVolumeHigh'
        document = plistlib.loads((workflow / 'Resources/document.wflow').read_bytes())
        assert document['workflowMetaData']['serviceApplicationBundleID'] == 'com.apple.finder'
        command = document['actions'][0]['action']['ActionParameters']['COMMAND_STRING']
        env = dict(os.environ, FINDER_AUDIO_NONINTERACTIVE='1', FINDER_AUDIO_LOG_DIR=str(base / 'Logs'))
        if mode != 'custom':
            result = subprocess.check_output(['/bin/zsh', '-c', command, 'workflow', str(source)], env=env, text=True)
            report = json.loads(result)
            assert report[0]['status'] == 'success'
            assert report[0]['channels'] == (1 if mode == 'mono' else 2)
        else:
            subprocess.run([sys.executable, str(runtime / 'audio_convert.py'), mode, '--settings-json',
                            '{"format":"flac","depth":"24","channels":"mono"}', str(source)], env=env, check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(runtime / 'Finder Audio Converter.app')], check=True)
    # Preference helper must preserve unrelated keys and entries in a disposable domain.
    domain = 'io.github.nearfield.finder-audio.test.' + uuid.uuid4().hex
    try:
        subprocess.run(['/usr/bin/defaults', 'write', domain, 'Sentinel', '-string', 'keep me'], check=True)
        subprocess.run(['/usr/bin/defaults', 'write', domain, 'NSServicesStatus', '-dict', 'unrelated', 'keep'], check=True)
        helper = [str(runtime / 'ServicePreferences')]
        subprocess.run(helper + ['enable', domain, str(runtime / 'service-keys.json')], check=True)
        preferences = plistlib.loads(subprocess.check_output(['/usr/bin/defaults', 'export', domain, '-']))
        assert preferences['Sentinel'] == 'keep me'
        assert preferences['NSServicesStatus']['unrelated'] == 'keep'
        keys = json.loads((runtime / 'service-keys.json').read_text())
        for key in keys:
            assert preferences['NSServicesStatus'][key]['presentation_modes']['ContextMenu'] is True
        subprocess.run(helper + ['remove', domain, str(runtime / 'service-keys.json')], check=True)
        preferences = plistlib.loads(subprocess.check_output(['/usr/bin/defaults', 'export', domain, '-']))
        assert preferences['NSServicesStatus'] == {'unrelated': 'keep'}
    finally:
        subprocess.run(['/usr/bin/defaults', 'delete', domain], check=False, capture_output=True)
    subprocess.run(args, check=True)
    assert list((base / 'Finder Audio Converter Backups').glob('*/runtime/manifest.json'))
    subprocess.run(args + ['--uninstall'], check=True)
    assert not runtime.exists()
    assert sentinel.read_text() == 'keep me'
    assert len(list(services.iterdir())) == 1
    assert source.exists() and list((base / 'Converted').iterdir())
print('PASS: isolated install, signed app, stock icons, workflow quoting, headless conversions, preference merge, upgrade and uninstall')
