# Usage

## Starting the application

### Installed with the Windows installer

Search for "Yaas" in your installed applications and start it.

### Installed with the macOS installer or the Linux AppImage

Launch it like any other application (from `/Applications` on macOS, or by
running the `.AppImage` file on Linux).

### Installed with uv / pip

Activate your virtual environment and run:

```bash
yaas
```

## Extracting stems

1. Use the embedded browser to search for or navigate to the video you want.
   A playlist page (`youtube.com/playlist?list=...`) works too: all its
   videos are split, one after the other.
2. Click **Start**.
3. Wait — separation can take a while, especially on CPU. The progress bar
   follows the download, the model download on first use, and the
   separation itself.
4. When the job is done, the status log lists the written stems: click one
   to open it. They're in the output folder set in **Settings...**
   (`$HOME/yaas_tracks` by default; `--out` overrides it for a single run
   without changing the saved setting), which **Open Output Folder** in the
   ☰ menu also opens.

### Queueing jobs

You don't have to wait for a job to finish to prepare the next one: while
one runs, keep browsing, and click **Add to Queue** (the **Start** button's
label while a job runs) on each video you want. Queued jobs run one at a
time, in order, each with the output folder and model set when it was
queued.

The job list, left of the status log, shows each job's state. Right-click a
job to remove it from the queue, open its output folder or show it in the
browser again, or to clear the finished jobs. Double-clicking a finished job
opens its output folder.

### Stopping a job

Click the red **Stop** button to stop the running job, whatever it's doing
(downloading, separating, or downloading a model); the next queued one then
starts. The separation runs in a separate process, which Stop ends
immediately. Stems already written are kept.

Closing Yaas while a job runs asks for confirmation, then stops it and
drops the queued jobs.

!!! note
    Respect the copyright of the video's authors. If they don't authorize
    sharing, keep your extracted stems for personal use only.

## The menu

The ☰ button to the right of the URL bar opens a menu with:

- **Settings...** — set the output folder extracted stems are written to,
  picked via your system's native folder picker, the separation model
  (see below), and the stems' sample rate: 48 kHz (default) or 44.1 kHz.
  The models work at 44.1 kHz; 48 kHz stems are resampled afterwards, so
  that DAWs working at 48 kHz can import them without converting them.
- **Open Output Folder** — opens the output folder in your file manager.
- **Documentation** — opens this site in your browser.
- **Report an Issue** — opens the GitHub issue tracker.
- **GPU Acceleration...** — on Windows/Linux, install, reinstall, or
  remove an on-demand CUDA-accelerated environment; see
  [Installation](installation.md#enabling-gpu-acceleration-in-the-windowslinux-installers).
  On Apple Silicon Macs, shows whether the built-in Metal (MPS) acceleration
  is available; see
  [Installation](installation.md#gpu-acceleration-on-macos).
- **About Yaas** — shows the installed version and license.

## Choosing a separation backend

Pick the separation model in **Settings...**: BS-Roformer (default),
HTDemucs 6 stems, or OpenUnmix. The choice is saved for future runs. It can
also be overridden for a single run from the command line.

Yaas supports two backends for splitting the soundtrack into stems:

1. **audio-separator** (default) — uses the
   [audio-separator](https://github.com/nomadkaraoke/python-audio-separator)
   library. Choose a model with `--model`:
      - `roformer` (default)
      - `htdemucs6s`
2. **OpenUnmix** — uses the
   [OpenUnmix](https://github.com/sigsep/open-unmix-pytorch) model.

```bash
# audio-separator with a specific model
yaas --backend audio_separator --model htdemucs6s

# OpenUnmix backend
yaas --backend openunmix
```

## Command-line options

| Option | Default | Description |
| --- | --- | --- |
| `--version` | | Print Yaas' version and exit. |
| `-o`, `--out DIR` | Settings dialog's output folder | Directory to store the output files in, for this run only. |
| `--backend {audio_separator,openunmix}` | Settings dialog's model | Track separation backend, for this run only. |
| `--model {roformer,htdemucs6s}` | Settings dialog's model | Model used by the `audio_separator` backend, for this run only. |
| `--sample-rate {44100,48000}` | Settings dialog's sample rate (48000) | Sample rate of the written stems, for this run only. |
