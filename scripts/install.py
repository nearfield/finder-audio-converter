#!/usr/bin/env python3
"""Build and install user-local Finder Quick Actions without GUI automation."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PROJECT = 'io.github.nearfield.finder-audio'
APP = 'Finder Audio Converter.app'
ACTIONS = [('mono', 'Downmix to Mono'), ('mp3', 'MP3 256 kbps'), ('custom', 'Custom Settings…')]
DEFAULT_RUNTIME = Path.home() / 'Library/Application Support/Finder Audio Converter'
DEFAULT_SERVICES = Path.home() / 'Library/Services'


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def tool(name):
    for candidate in [os.environ.get('FINDER_AUDIO_' + name.upper()), shutil.which(name),
                      '/opt/homebrew/bin/' + name, '/usr/local/bin/' + name]:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return str(Path(candidate).absolute())
    raise RuntimeError(name + ' is missing. Run ./install.sh --bootstrap or install it yourself.')


def owned_runtime(path):
    try:
        return json.loads((path / 'manifest.json').read_text())['project'] == PROJECT
    except (OSError, ValueError, KeyError):
        return False


def owned_workflow(path, legacy=False):
    try:
        info = plistlib.loads((path / 'Contents/Info.plist').read_bytes())
        identifier = info.get('CFBundleIdentifier', '')
        if identifier in [PROJECT + '.' + mode for mode, _ in ACTIONS]:
            return True
        if legacy:
            data = plistlib.loads((path / 'Contents/Resources/document.wflow').read_bytes())
            command = data['actions'][0]['action']['ActionParameters']['COMMAND_STRING']
            return ('finder-audio-converter/audio_convert.py' in command and
                    (identifier.startswith('local.') or not identifier))
    except (OSError, ValueError, KeyError, IndexError):
        pass
    return False


def build(folder, runtime, services):
    runtime_build = folder / 'runtime'
    runtime_build.mkdir()
    shutil.copy2(ROOT / 'src/audio_convert.py', runtime_build)
    config = {name: tool(name) for name in ['ffmpeg', 'ffprobe']}
    for binary in config.values():
        subprocess.run([binary, '-version'], check=True, stdout=subprocess.DEVNULL)
    encoders = subprocess.check_output([config['ffmpeg'], '-hide_banner', '-encoders'], text=True)
    if 'libmp3lame' not in encoders:
        raise RuntimeError('FFmpeg must include the libmp3lame encoder.')
    (runtime_build / 'config.json').write_text(json.dumps(config, indent=2))
    contents = runtime_build / APP / 'Contents'
    (contents / 'MacOS').mkdir(parents=True)
    (contents / 'Resources').mkdir()
    target = platform.machine() + '-apple-macos13.0'
    for source, output in [('AudioDialog', contents / 'MacOS/AudioDialog'),
                           ('ExportSystemIcon', folder / 'ExportSystemIcon'),
                           ('ServicePreferences', runtime_build / 'ServicePreferences')]:
        run('/usr/bin/xcrun', 'swiftc', '-O', '-target', target, ROOT / 'native' / (source + '.swift'), '-o', output)
    icon_folder = folder / 'icons'
    run(folder / 'ExportSystemIcon', icon_folder)
    chunks = b''
    for size, kind in [(16,b'icp4'),(32,b'icp5'),(64,b'icp6'),(128,b'ic07'),(256,b'ic08'),(512,b'ic09'),(1024,b'ic10')]:
        png = (icon_folder / (str(size) + '.png')).read_bytes()
        chunks += kind + struct.pack('>I', len(png) + 8) + png
    (contents / 'Resources/AudioConverter.icns').write_bytes(b'icns' + struct.pack('>I', len(chunks) + 8) + chunks)
    info = dict(CFBundleIdentifier=PROJECT + '.dialog', CFBundleName='Finder Audio Converter',
                CFBundleDisplayName='Finder Audio Converter', CFBundleExecutable='AudioDialog',
                CFBundlePackageType='APPL', CFBundleShortVersionString='1.0.0', CFBundleVersion='1',
                LSMinimumSystemVersion='13.0', CFBundleDevelopmentRegion='en', CFBundleLocalizations=['en'],
                CFBundleIconFile='AudioConverter')
    (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
    run('/usr/bin/codesign', '--force', '--sign', '-', contents.parent)
    run('/usr/bin/codesign', '--verify', '--strict', contents.parent)
    run(sys.executable, ROOT / 'scripts/build_workflows.py', '--output', runtime_build,
        '--runtime', runtime, '--python', os.path.abspath(sys.executable))
    keys = [PROJECT + '.' + mode + ' - ' + name + ' - runWorkflowAsService' for mode, name in ACTIONS]
    (runtime_build / 'service-keys.json').write_text(json.dumps(keys))
    (runtime_build / 'manifest.json').write_text(json.dumps({
        'project': PROJECT, 'version': '1.0.0', 'services': str(services), 'python': os.path.abspath(sys.executable),
        'workflows': [name + '.workflow' for _, name in ACTIONS]}, indent=2))
    return runtime_build


def preferences(runtime, mode, domain):
    run(runtime / 'ServicePreferences', mode, domain, runtime / 'service-keys.json')
    if domain == 'pbs':
        run('/System/Library/CoreServices/pbs', '-update')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument('--services-dir', type=Path, default=DEFAULT_SERVICES)
    parser.add_argument('--skip-register', action='store_true', help='Build/install in isolation without changing service preferences.')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or int(platform.mac_ver()[0].split('.')[0]) < 13:
        raise RuntimeError('macOS 13 or later is required.')
    if os.getuid() == 0:
        raise RuntimeError('Run as your normal user, not with sudo.')
    runtime, services = args.prefix.expanduser().absolute(), args.services_dir.expanduser().absolute()
    if not args.skip_register and (runtime != DEFAULT_RUNTIME or services != DEFAULT_SERVICES):
        raise RuntimeError('Custom locations require --skip-register to protect your actual Finder services.')
    if runtime.is_symlink() or services.is_symlink():
        raise RuntimeError('Installation directories must not be symlinks.')
    if runtime == services or runtime in services.parents or services in runtime.parents:
        raise RuntimeError('Runtime and Services directories must be separate.')
    if runtime.exists() and not owned_runtime(runtime):
        raise RuntimeError('Refusing to replace an unrecognized directory: ' + str(runtime))
    # An active conversion may still need the current helper and configuration.
    processes = subprocess.check_output(['/bin/ps', '-axo', 'args='], text=True)
    if any(str(runtime / 'audio_convert.py') in line or str(runtime / APP / 'Contents/MacOS/AudioDialog') in line
           for line in processes.splitlines()):
        raise RuntimeError('Close converter dialogs and wait for conversions to finish, then retry.')
    if args.uninstall:
        if not runtime.exists():
            print('Nothing to uninstall.'); return
        manifest = json.loads((runtime / 'manifest.json').read_text())
        if manifest['services'] != str(services):
            raise RuntimeError('Services directory does not match the installation manifest.')
        if not args.skip_register:
            preferences(runtime, 'remove', 'pbs')
        for _, name in ACTIONS:
            destination = services / (name + '.workflow')
            if destination.is_symlink():
                raise RuntimeError('Refusing to remove a symlink: ' + str(destination))
            if owned_workflow(destination):
                shutil.rmtree(destination)
        shutil.rmtree(runtime)
        if not args.skip_register:
            run('/System/Library/CoreServices/pbs', '-update')
        print('Uninstalled. Source audio, converted files, logs, dependencies and backups were kept.')
        return
    for _, name in ACTIONS:
        destination = services / (name + '.workflow')
        if destination.is_symlink() or (destination.exists() and not owned_workflow(destination, legacy=True)):
            raise RuntimeError('A different workflow already uses this name: ' + str(destination))
    runtime.parent.mkdir(parents=True, exist_ok=True)
    services.mkdir(parents=True, exist_ok=True)
    # Build first: compiler, dependencies and icon failures leave the current installation intact.
    with tempfile.TemporaryDirectory(prefix='.finder-audio-build-', dir=runtime.parent) as temporary:
        staged = build(Path(temporary), runtime, services)
        backup = runtime.parent / 'Finder Audio Converter Backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True)
        saved, installed = [], []
        try:
            for current, previous in [(runtime, backup / 'runtime')] + [
                    (services / (name + '.workflow'), backup / (name + '.workflow')) for _, name in ACTIONS]:
                if current.exists():
                    shutil.move(str(current), str(previous)); saved.append((current, previous))
            for _, name in ACTIONS:
                destination = services / (name + '.workflow')
                shutil.move(str(staged / 'workflows' / (name + '.workflow')), str(destination))
                installed.append(destination)
            (staged / 'workflows').rmdir()
            shutil.move(str(staged), str(runtime)); installed.append(runtime)
            if not args.skip_register:
                preferences(runtime, 'enable', 'pbs')
        except Exception:
            for path in reversed(installed):
                shutil.rmtree(path)
            for current, previous in reversed(saved):
                shutil.move(str(previous), str(current))
            raise
    print('Installed three Quick Actions with the macOS Audio Output icon.')
    print('Runtime: ' + str(runtime))
    print('Backup: ' + str(backup))
    if not args.skip_register:
        print('Select audio files in Finder, then right-click > Quick Actions.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
