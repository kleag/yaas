# Changelog

## 1.0.0

New features:

- Job queue: while a job runs, **Add to Queue** prepares the next ones,
  which then run in order. The job list shows each job's state, with
  actions on right-click.
- Playlists: a playlist page's videos are all split, one after the other.
- Links to the written stems in the status log, and an **Open Output
  Folder** menu entry.
- Progress is also shown while downloading the video and the model.
- More YouTube URLs are recognized: `youtu.be`, Shorts, live videos,
  `m.youtube.com` and YouTube Music.
- `--version` option.
- Stems are written at 48 kHz by default, the usual rate of DAW sessions,
  which then don't have to convert them on import. The models still work
  at 44.1 kHz; the stems are resampled afterwards. 44.1 kHz can be chosen
  in **Settings...**, or for one run with `--sample-rate`.

Fixes:

- **Stop** now stops the job immediately and cleanly, at any step, instead
  of abruptly killing the thread: the separation runs in a child process,
  which Stop ends, and the job's intermediate files are removed. An
  interrupted model download no longer leaves a truncated model behind.
  The button is red.
- GPU acceleration on Windows: the GPU environment got PyPI's CPU-only
  PyTorch. It now gets PyTorch's CUDA build (CUDA 13 for Blackwell GPUs).
- OpenUnmix produces stereo stems (they were mono), and is given the
  audio's actual sample rate.
- The audio is decoded straight to FLAC, without the lossy MP3 step, which
  degraded the separation's input.
- A failed step no longer reports "Extraction complete", and errors are
  reported once, with their cause.
- Closing Yaas during a job no longer crashes it.

Other changes:

- Removed the unused `ffmpeg` PyPI dependency (Yaas uses the ffmpeg program).
- Test suite, run by CI.

Yaas is versioned with [bumpver](https://github.com/mbarkhau/bumpver) and
released via tagged GitHub Releases.

See the [GitHub Releases page](https://github.com/kleag/yaas/releases) for
the full history of published versions and their artifacts, and the
[commit history](https://github.com/kleag/yaas/commits/main/) for
day-to-day changes.
