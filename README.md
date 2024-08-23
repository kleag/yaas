# Yet Another Audio Splitter

This is Yaas 0.4.0, a tool to split video soundtracks into separate tracks
using OpenUnmix.

## Installation

```bash
pip install yaas
```

## Usage

Just run

```
yaas
```

Search the video from which you want to extract the sound tracks using the
integrated browser, click the Start button, wait, and then use the generated
audio files.

Note that you must respect the copyright of the authors. E.g., If they don't
authorize sharing, you must keep your private copy for you.

## Building and distributing

```bash
git commit
bumpver update --patch
python -m build
twine upload dist/*
```

## Author

Gaël de Chalendar, aka Kleag
(c) Gaël de Chalendar, 2024

This program is free software, licensed under the Mozilla Public License 2.0
(MPL 2.0) license (see the LICENSE file). It includes most of the
youtube-to-mp3 project (https://github.com/cedricouellet/youtube-to-mp3),
itself under the MPL license.


