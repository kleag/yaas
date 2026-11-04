# Testing on Windows in a VM

How to run a manual test pass of the Windows installer on a Linux machine, with
no prior experience of virtual machines. It assumes Ubuntu and an x86_64 CPU.

CI already builds the installer and runs `--self-test` on real Windows. This
pass covers what CI doesn't: the installer, the embedded browser, real
separations, Stop, and a user account with accents in its name.

**Not covered:** CUDA. It needs an NVIDIA GPU passed through to the VM, so test
it on a real Windows machine with an NVIDIA card.

The steps use [quickemu](https://github.com/quickemu-project/quickemu), a small
wrapper around QEMU/KVM:

- QEMU emulates a PC, KVM makes it fast, and quickemu picks the settings.
- A VM is just a folder and a config file. Deleting them removes it.
- Its networking doesn't use a bridge, so it works next to Docker and UFW, which
  can cut a VM's internet access under libvirt/virt-manager.
- `quickget` installs Windows unattended, including the VirtIO drivers and a
  local account, so no Microsoft account is needed.

Allow about 1 hour for the setup (mostly unattended) and 1 to 3 hours for the
test pass, since separation on CPU is slow.

## Disk use

Everything goes on the host disk, in the folder you create in step 2. Sizes
marked ~ are estimates; the others come from the 1.0.0 release and from model
files downloaded on Linux.

| Item | Size | Notes |
| --- | --- | --- |
| quickemu and its dependencies | ~100 MB | apt shows the exact figure |
| Windows ISO | ~8 GB | Can be deleted after install (step 5) |
| VirtIO drivers ISO | ~750 MB | Can be deleted after install (step 5) |
| VM disk (`disk.qcow2`), fresh Windows | ~25 GB | Grows as needed, up to about 64 GB |
| Windows updates | ~5-10 GB | Inside the VM disk |
| Snapshot | starts near 0 | Grows as Windows rewrites data after it's taken |

Yaas uses this inside the VM disk:

| Item | Size | Notes |
| --- | --- | --- |
| Installer | 531 MiB | |
| Installed `yaas.exe` | ~530 MiB | |
| Extraction to `%TEMP%\_MEI*` | ~3.6 GB | While running; based on a Linux build; see the note below |
| BS-Roformer model | 699 MB | Kept in the cache |
| OpenUnmix model | 452 MB | Kept in the cache |
| HTDemucs 6 stems model | ~55 MB | Kept in the cache |
| Browser cache | ~250 MB | |
| ffmpeg | ~500 MB | |
| Stems for a 4-minute song | 180-550 MB | 4 to 6 WAV files, depending on model and format |
| GPU environment (optional) | several GB | Skip it: no use without an NVIDIA GPU |

Yaas's single-file build unpacks itself to `%TEMP%` at each launch and removes
that copy on a clean exit. A killed or crashed yaas can leave ~3.6 GB behind,
which the test pass checks.

**Budget 60 GB free before starting.** A full pass should stay around 45-55 GB,
but check with `du -sh` as you go. The VM disk never shrinks by itself, even if
you delete files inside Windows; deleting the VM (step 8) gets it all back.

If you back up your home folder, exclude the VM folder.

## 1. Check the host and install quickemu

```bash
df -h ~                       # at least 60 GB available
ls -l /dev/kvm                # must exist
test -r /dev/kvm -a -w /dev/kvm && echo "KVM OK" || echo "no KVM access"
sudo apt install quickemu
```

If `/dev/kvm` is missing, enable virtualization (VT-x or AMD-V) in the BIOS/UEFI
settings. If it exists but you have no access, run
`sudo usermod -aG kvm "$USER"`, then log out and back in.

On a recent Intel CPU with performance and efficiency cores, Windows guests can
hang or crash on low-level CPU register accesses that KVM doesn't handle. Have KVM
ignore them (quickemu also warns about this setting at startup). This lasts until
the host reboots, so run it again after a reboot:

```bash
echo Y | sudo tee /sys/module/kvm/parameters/ignore_msrs
```

To make it permanent, use
`echo "options kvm ignore_msrs=Y" | sudo tee /etc/modprobe.d/kvm-quickemu.conf`.

## 2. Download Windows and create the VM

```bash
mkdir -p ~/VMs && cd ~/VMs
quickget windows 11
```

This downloads the Windows 11 ISO from Microsoft and the VirtIO drivers, then
creates `windows-11.conf` and a `windows-11/` folder. A different language can
be requested, e.g. `quickget windows 11 "French"`.

This is the regular Windows 11 ISO, **not** the 90-day evaluation. It runs
unactivated, showing a watermark and with personalization settings locked,
which doesn't affect the tests. Microsoft's license terms still expect a license
for it; if that matters for your use, see
[Using the 90-day evaluation instead](#using-the-90-day-evaluation-instead).

If Microsoft blocks the download, quickget says so and still creates the VM. In
that case:

1. Get the "Windows 11 Disk Image (ISO) for x64 devices" from
   <https://www.microsoft.com/software-download/windows11> in a browser.
2. Save it as `~/VMs/windows-11/windows-11.iso`.

Now give the VM more resources than the defaults, as separation is heavy. Adjust
these to your machine, leaving the host enough to work with:

```bash
cat >> windows-11.conf <<'EOF'
ram="16G"
cpu_cores="8"
EOF
```

## 3. Install Windows

```bash
quickemu --vm windows-11.conf
```

A window opens and Windows installs itself, restarting a few times. Don't
interact with it unless it stops at a question. This takes about 20-40 minutes.
It ends on the desktop, logged in as user `Quickemu`, password `quickemu`.

To use the VM window:

- Click inside to capture the mouse and keyboard, and press **Ctrl+Alt+G** to
  release them.
- There's no copy and paste with the host in this default display mode, so URLs
  below are kept short.
- Shut down from the Windows Start menu, which also closes the VM.
- The keyboard follows the layout set in Windows, not the host's: US QWERTY at
  first. On an AZERTY keyboard, type `quickemu` as if on QWERTY (`q` is the `A`
  key, `m` is the `,` key), or add your layout in **Settings > Time & language >
  Language & region**.

If quickemu reports a TPM or `swtpm` permission error (AppArmor can block it on
Ubuntu), change `tpm="on"` to `tpm="off"` in `windows-11.conf`. The unattended
install skips Windows 11's TPM check, and yaas doesn't need a TPM.

## 4. Prepare a test account

Yaas should work for a user whose name has accents and a space, since these end
up in its data paths. In the VM, right-click Start, open **Terminal (Admin)**, and
run:

```powershell
$name = "$([char]0xC9)lo$([char]0xEF)se Test"    # "Éloïse Test", on any keyboard
$pw = Read-Host -AsSecureString "Password for the test account"
New-LocalUser -Name $name -Password $pw
Add-LocalGroupMember -Group "Users" -Member $name
```

Then, still as `Quickemu`:

1. Run **Settings > Windows Update** until no more updates are offered, then
   choose **Pause updates**, so they don't eat disk or CPU during the tests.
2. Sign out, log in once as `Éloïse Test` so that the profile gets created, and
   wait a few minutes: this is also when `winget` becomes available to this user.
3. Shut down from the Start menu.

## 5. Free the ISOs and take a clean snapshot

The ISOs aren't needed anymore. Remove their lines from the config, then delete
them:

```bash
cd ~/VMs
sed -i -E '/^(iso|fixed_iso)=/d' windows-11.conf
du -h windows-11/*.iso                  # see what you're about to delete
rm windows-11/*.iso
du -sh windows-11                       # current size of the VM
```

Now save this clean state, before ffmpeg and yaas exist on it. With the VM shut
down:

```bash
quickemu --vm windows-11.conf --snapshot create clean
```

To retest from scratch later (for example on a new build), go back to it:

```bash
quickemu --vm windows-11.conf --snapshot apply clean
```

## 6. Get the installer into the VM

Start the VM with `quickemu --vm windows-11.conf` and log in as `Éloïse Test`.

**Published release:** open Edge in the VM and go to the releases page,
<https://github.com/kleag/yaas/releases>, then download `yaas_installer.exe`.
This is what users do, so it also shows you the warnings they get.

**Unreleased code:** build it with the release workflow from the branch you
pushed, which takes a while and creates no release. On the host:

```bash
gh workflow run release.yml --ref <branch>
gh run list --workflow=release.yml --limit 1     # note the run's ID
gh run watch <run-id>
gh run download <run-id> -n yaas_installer_windows -D ~/VMs/build
python3 -m http.server --bind 127.0.0.1 8000 -d ~/VMs/build
```

Then, in Edge in the VM, go to `http://10.0.2.2:8000/yaas_installer.exe`. From
inside the VM, `10.0.2.2` is the host's localhost. Stop the server with Ctrl+C
when done.

## 7. Run the test pass

Choose a short video of 2-3 minutes: a CPU separation can take far longer than
the song. A slow or stuttering YouTube video isn't a yaas bug, as the VM has no
GPU acceleration.

Expected data locations (if one differs, note it and search for `yaas` under
`%APPDATA%` and `%LOCALAPPDATA%`):

| What | Where |
| --- | --- |
| Job temp folders | `%APPDATA%\yaas\work` |
| audio-separator models | `%LOCALAPPDATA%\yaas\cache\audio-separator-models` |
| OpenUnmix models | `%USERPROFILE%\.cache\torch\hub\checkpoints` |
| Stems | `%USERPROFILE%\yaas_tracks` |

### Install, without ffmpeg

- [ ] Note any Edge or SmartScreen warning. On "Windows protected your PC",
      choose **More info > Run anyway**.
- [ ] The installer asks for admin rights (user `Quickemu`, password `quickemu`)
      and finishes.
- [ ] Start Yaas from the Start menu: a "FFMPEG Check" error appears, and the app
      exits cleanly. Note how long startup takes (a single-file build is slow,
      and Defender scans it).

### Install ffmpeg as the README says

- [ ] In a terminal, `winget install ffmpeg` succeeds.
- [ ] Yaas now starts from the Start menu, with no error. If it still reports no
      ffmpeg, retry after signing out and in, and note this: the README would
      need to mention it.

### Self-test

- [ ] In PowerShell, this ends with `Self-test passed` and `0`:

```powershell
$p = Start-Process "$env:ProgramFiles\YAAS\yaas.exe" -ArgumentList '--self-test',"$env:USERPROFILE\selftest.txt" -Wait -PassThru
Get-Content "$env:USERPROFILE\selftest.txt"
$p.ExitCode
```

### Window and browser

- [ ] The window icon and title are right; resizing works.
- [ ] YouTube loads, the cookie prompt can be answered, a video plays with sound.
- [ ] Typing in YouTube's search box works.
- [ ] ☰ menu: **Settings...**, **Open Output Folder**, **Documentation**, **Report
      an Issue** and **About Yaas** (right version) all work.

### Separation

For each model, chosen in **Settings...**: click **Start** on your video.

- [ ] BS-Roformer: the model download shows progress, then separation does, and
      WAV files appear.
- [ ] HTDemucs 6 stems: produces 6 files, including guitar and piano.
- [ ] OpenUnmix: produces 4 files.
- [ ] Each stem link in the status log opens in the default player, and it sounds
      right.
- [ ] A WAV's **Properties > Details** shows the sample rate from Settings (48 kHz
      by default).
- [ ] `%APPDATA%\yaas\work` is empty after each job.
- [ ] Second run of a model: no new download.

### Paths

- [ ] In **Settings...**, an output folder with a space and an accent (e.g.
      `Documents\Mes morceaux é`) works, and **Open Output Folder** opens it.
- [ ] A video whose title has characters forbidden in Windows file names
      (`: ? " / | *`) or non-Latin ones produces stems, with usable links.

### Stop

- [ ] Stop during the download: job ends as cancelled, temp folder removed.
- [ ] Stop during separation: the status changes promptly, Task Manager shows no
      separation process left working (only the main `yaas.exe` processes, with
      CPU near 0), and the `work` folder gets emptied. "File in use" problems,
      which Linux doesn't have, would show here.
- [ ] Stop during a first-time model download (delete the model from the cache
      to test), then Start again: it downloads again and works.
- [ ] A new job after each Stop works.

### Queue and playlist

- [ ] While a job runs, browse to another video and click **Add to Queue**: the
      jobs run in order.
- [ ] Remove a queued job with a right-click.
- [ ] A short playlist produces stems for each of its videos.

### Closing and leftovers

- [ ] Close the window with a job running: `yaas.exe` and its child processes
      disappear from Task Manager within a few seconds.
- [ ] Look for `_MEI*` folders in `%TEMP%`, and note their size. Clean exits
      should leave none; note whether a close during a job, or killing yaas from
      Task Manager, leaves them, and whether they pile up over launches.
- [ ] After such a close, the next launch works, and stale `work` folders get
      removed.

### GPU dialog (no NVIDIA GPU)

- [ ] ☰ > **GPU Acceleration...** opens and reads sensibly. Click **Cancel**.
      Installing downloads several GB and can only end with "no CUDA-capable GPU
      detected", so skip it unless you're testing this message.

### Uninstall

- [ ] **Settings > Apps > Installed apps > Yaas > Uninstall** removes it, and the
      Start menu entry. Note what's left in `%APPDATA%`, `%LOCALAPPDATA%`,
      `%USERPROFILE%\.cache` and `yaas_tracks`.
- [ ] Reinstalling works.

## 8. Clean up

Keep the VM, and its snapshot, as long as you might retest. If disk space runs
low, go back to the clean snapshot (step 5), or delete it once you no longer need
it, with `--snapshot delete clean`. Snapshot data inside the file may not return
to the host, though, so only deleting the VM is sure to free the space.

To delete everything:

```bash
cd ~/VMs
quickemu --vm windows-11.conf --delete-vm    # deletes the windows-11 folder and config
rm -rf ~/VMs/build                           # if you used it
du -sh ~/VMs
sudo apt remove quickemu                     # optional; `sudo apt autoremove` for its dependencies
```

## Using the 90-day evaluation instead

Microsoft offers a
[Windows 11 Enterprise evaluation](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise),
free after registration. It costs more effort, as the unattended install doesn't
apply:

- Its page says that you must sign in with a Microsoft account. Have one ready.
- Choose the regular ISO, not LTSC: LTSC has no Microsoft Store, and so no
  `winget`, which the README relies on.
- After 90 days, the desktop turns black and the PC shuts down every hour, so
  recreate the VM rather than keeping it.

Follow step 2, which still sets up the VM and the drivers, and save the evaluation
ISO in `~/VMs/windows-11/`. Then make the VM use it for a manual install, removing
the regular ISO if quickget downloaded it:

```bash
cd ~/VMs
ls -lh windows-11/*.iso
rm windows-11/unattended.iso
rm windows-11/Win11*.iso                # the regular ISO, if there's one
sed -i 's|^iso=.*|iso="windows-11/your-evaluation.iso"|' windows-11.conf
quickemu --vm windows-11.conf
```

Windows setup then asks its questions, and won't see the disk at first: choose
**Load driver**, and browse the VirtIO CD to `viostor\w11\amd64`.

The account sign-in needs internet, but the network card has no driver yet. On the
"connect to a network" screen, look for an option to install a driver, and browse
to `NetKVM\w11\amd64` on the same CD. This screen changes between Windows
releases, and these steps haven't been tried on the current one.

After the install, run `virtio-win-gt-x64.msi` from the CD for the other drivers.
Then go on with step 4, substituting your own admin account for `Quickemu`.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Windows hangs or blue-screens at boot or during install | Check `cat /sys/module/kvm/parameters/ignore_msrs` shows `Y` (step 1), then start the VM again |
| `winget` isn't recognized | Wait a few minutes after the first login. If it persists, run `Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe` |
| Edge blocks the `http://10.0.2.2` download | Choose **Keep** in the downloads list |
| Very slow VM | Check that quickemu's startup output doesn't complain about KVM, and lower `cpu_cores` if the host is starving |
| Stuck on a boot screen or UEFI shell during install | Close the VM and run `quickemu --vm windows-11.conf` again |
| The display freezes | The default display (`sdl`) is the safe one; quickemu's wiki reports freezes with `--display spice` on Windows guests |
| Separation killed, or out-of-memory errors | Raise `ram` in `windows-11.conf`, with the VM shut down |
| Windows disk full | Delete stems, models and `%TEMP%\_MEI*` folders in the VM, or go back to the snapshot |
| Host disk running full | Shut down the VM and see [Clean up](#8-clean-up) |
| VM asks for activation | Expected, with the regular ISO; ignore it |
