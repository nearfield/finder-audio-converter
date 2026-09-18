# Finder Audio Converter

Four English-language audio Quick Actions for macOS Finder, installed entirely from Terminal:

- **Downmix to Mono** — average stereo left/right channels; preserve the supported source format, sample rate and PCM bit depth.
- **MP3 256 kbps** — 256 kbps CBR with LAME's highest quality setting; preserve supported source sample rates and mono/stereo channels.
- **Custom Settings…** — choose format, sample rate, channels, bit depth and bitrate in a native macOS window.
- **Pad to Next 5 Seconds** — append digital silence to reach the next 5-second boundary and save as WAV.

All four live under **right-click → Quick Actions** and use macOS's built-in **Audio Output** speaker image (`NSTouchBarAudioOutputVolumeHigh`). Dialogs use the same image. Apple artwork is obtained from the local OS during installation, never bundled in this repository.

## Install

Run as your normal logged-in macOS user. Do not run the whole installer with `sudo`.

```sh
mkdir -p ~/Developer
cd ~/Developer
git clone https://github.com/nearfield/finder-audio-converter.git
cd finder-audio-converter
./install.sh --bootstrap
```

`--bootstrap` explicitly opts into installing Homebrew (if absent), Apple Command Line Tools, Python and FFmpeg. Homebrew installation may require an administrator password **in Terminal**. No Automator editing, icon picker or computer-use automation is involved. Network access is needed only to download dependencies/source. Conversion runs locally.

On a fresh Mac without Git/Command Line Tools, download the source with built-in tools first:

```sh
mkdir -p ~/Developer
cd ~/Developer
curl --fail --location https://github.com/nearfield/finder-audio-converter/archive/refs/heads/main.tar.gz -o finder-audio-converter.tar.gz
tar -xzf finder-audio-converter.tar.gz
cd finder-audio-converter-main
./install.sh --bootstrap
```

Use an empty destination for either method. If dependencies are already installed, simply run `./install.sh` (no network needed).

The application targets **macOS 13+** and builds for the current Mac architecture. The dependency bootstrap follows [Homebrew's current platform requirements](https://docs.brew.sh/Installation); older macOS/Intel systems may need independently installed dependencies. Actual validation to date: Apple Silicon, macOS 26.6.2. A pristine machine without development tools has not been tested.

Required tools: Python 3.9+, FFmpeg/ffprobe with `libmp3lame`, Apple Command Line Tools including Swift. No Python packages are required. Existing tools are discovered through `PATH`, `/opt/homebrew/bin`, and `/usr/local/bin`. Override with `FINDER_AUDIO_PYTHON`, `FINDER_AUDIO_FFMPEG`, and `FINDER_AUDIO_FFPROBE` if needed.

## Use

Select one or more audio files in Finder, then right-click → **Quick Actions**. The selected preset applies to the whole batch. Each source gets a neighboring `Converted` folder; originals are never modified and existing outputs are never overwritten. Numeric suffixes resolve duplicate names.

Custom formats: WAV, AIFF, FLAC, MP3, M4A/AAC and M4A/Apple Lossless. Channel choices: keep original, mono downmix, left only, right only and stereo. WAV/AIFF also support 32-bit float. Integer bit-depth reduction uses triangular dithering. There is no loudness normalization.

Important format behavior:

- MP3 has **no PCM bit depth to preserve**. The 256 kbps preset requires 32, 44.1 or 48 kHz and one or two channels. Unsupported sources fail with an explanation; choose an explicit rate/downmix in Custom Settings.
- Fixed 256 kbps controls MP3 size. LAME quality `0` uses more encoder effort, not a smaller target bitrate.
- Stereo mono downmix is `(L + R) / 2`; multichannel sources use FFmpeg's channel-layout downmix. Already-mono files are skipped by the mono preset. Lossy formats require re-encoding.
- “Keep original” bit depth uses 24-bit for lossy sources. FLAC/ALAC require 16 or 24 bit; choose explicitly for float sources.
- Only files containing exactly one audio stream are supported. Ordinary text tags are copied where supported; artwork, BWF/iXML and every format-specific metadata field are not guaranteed.
- Publishing outputs uses an exclusive hard link to prevent overwrites; use a filesystem supporting hard links, such as APFS. FAT/exFAT destinations are not supported.

### Pad to Next 5 Seconds

Each selected file is independently rounded **up** to a multiple of 5 seconds: 28.2 → 30, 31.7 → 35, 37 → 40. Exact multiples stay the same length (30 → 30), with no extra silence. There is no settings dialog; the existing completion summary appears after processing.

Outputs are named `Converted/<name>_padded_30s.wav` (with numeric suffixes for collisions). This action always saves WAV, preserving the sample rate, channel count and supported PCM precision; lossy input becomes 24-bit PCM. It does not trim, fade, normalize or time-stretch audio.

The source is decoded to a temporary PCM WAV first, so the target is calculated from its **integer sample count**, not a rounded duration or an MP3/AAC container estimate. FFmpeg's [apad filter](https://ffmpeg.org/ffmpeg-filters.html#apad) appends zero-amplitude samples, and the output sample count and audio format are checked before publication. An input one sample past a boundary goes to the following boundary. Floating-point and multichannel PCM are supported. Temporary decoded/padded files require extra free disk space and are removed when processing finishes or fails.

For this action, original PCM sample values are preserved. Lossy input preserves the decoded signal at the output's 24-bit precision; it cannot recover information lost during compression. MP3/AAC decoder handling of encoder delay and end padding determines the decoded source length.

macOS's built-in **Encode Selected Audio Files** is separate and remains untouched.

## What installation does

1. Checks dependencies and builds a small Swift/AppKit dialog helper with a local ad-hoc signature.
2. Exports the stock system speaker image and generates four Automator workflow bundles.
3. Installs a self-contained runtime in `~/Library/Application Support/Finder Audio Converter` and workflows in `~/Library/Services`.
4. Enables only these four services in the current user's `pbs` service preferences and asks macOS to refresh service registration.

The source checkout can be moved or removed after installation. Dependency executables must remain available at their recorded paths; rerun installation after moving them. No background daemon, Finder extension process, server or startup item is installed.

Finder service preference storage is a macOS implementation detail. Registration is checked programmatically, but menu appearance can vary between OS releases. If Finder holds an old menu, close/reopen its window or log out/in. In restrictive managed environments, system policy may prevent enabling services. The installer does not change unrelated services or built-in Quick Actions.

Existing installations are built before replacement, then backed up under `~/Library/Application Support/Finder Audio Converter Backups`. A failed file deployment restores the previous bundles. Backups are kept for manual recovery; failed registration may leave this project's preference entries behind. Do not update during a conversion or while its dialog is open.

Logs live in `~/Library/Logs/Finder Audio Converter` and include local filenames and paths. They are never uploaded by the application.

## Update / uninstall

```sh
git pull --ff-only
./install.sh
# Remove only the installed runtime and this project's workflows:
./uninstall.sh
```

Uninstall preserves original audio, converted output, logs, backups and Homebrew dependencies. It does not restore earlier backed-up workflows automatically.

## Test without UI

```sh
python3 tests/test_conversion.py
python3 tests/test_padding.py
python3 tests/test_install.py
```

The conversion test checks waveform averaging, metadata, bitrate, unsupported inputs, collisions and source hashes. The padding test checks exact 30/35/40-second output, one-sample boundary cases, unchanged original samples, all-zero appended samples, compressed input, batch failures and cleanup. The install test uses temporary directories and a disposable preferences domain; it builds/signs the app, executes the generated workflow commands, checks stock icon references, repeats installation and uninstalls while preserving unrelated files. It does not open dialogs or modify your live Finder workflows.

An isolated build can also be installed manually with:

```sh
./install.sh --prefix /tmp/finder-audio-runtime --services-dir /tmp/finder-audio-services --skip-register
./uninstall.sh --prefix /tmp/finder-audio-runtime --services-dir /tmp/finder-audio-services --skip-register
```

The core supports headless use with `FINDER_AUDIO_NONINTERACTIVE=1` and a nonzero exit status if any file fails. Use `pad` for automatic 5-second WAV padding. Custom mode additionally requires `--settings-json`, for example:

```sh
FINDER_AUDIO_NONINTERACTIVE=1 python3 src/audio_convert.py custom \
  --settings-json '{"format":"flac","rate":48000,"channels":"mono","depth":"24"}' \
  '/path/to/audio.wav'
```

## License

Project source: MIT. macOS system images remain Apple's; dependencies retain their own licenses. FFmpeg, Python and system images are not distributed in this repository.
