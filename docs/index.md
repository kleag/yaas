# Yaas — Yet Another Audio Splitter

Yaas is a desktop application that splits a YouTube video's soundtrack into
separate stems (vocals, drums, bass, other, ...).

It works by:

1. embedding a browser so you can navigate to and pick a YouTube video,
2. downloading its audio and converting it to FLAC,
3. splitting the FLAC into stems using a machine-learning source-separation
   model (either [OpenUnmix](https://github.com/sigsep/open-unmix-pytorch)
   or [audio-separator](https://github.com/nomadkaraoke/python-audio-separator)),
4. writing the resulting WAV stems to an output directory (`$HOME/yaas_tracks`
   by default).

[:material-buy-me-a-coffee: Buy Gaël a coffee](https://www.buymeacoffee.com/kleag){ .md-button }

## Where to go next

- New to Yaas? Start with [Installation](installation.md).
- Already installed it? See [Usage](usage.md) for how to run an extraction
  and choose a separation backend.
- Want to build Yaas from source, package an installer, or cut a release?
  See [Building & Releasing](building.md).

## Copyright and licensing

Respect the copyright of the video authors. If they don't authorize
redistribution, keep your extracted stems for personal use only.

Yaas is free software, licensed under the
[Mozilla Public License 2.0 (MPL 2.0)](https://github.com/kleag/yaas/blob/main/LICENSE).
It includes parts of the
[youtube-to-mp3](https://github.com/cedricouellet/youtube-to-mp3) project,
also under the MPL license.

Gaël de Chalendar, aka Kleag — (c) Gaël de Chalendar, 2024-2026.
