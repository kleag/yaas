# Building & Releasing

## Development setup

Yaas uses [uv](https://docs.astral.sh/uv/) for environment and dependency
management. A `.venv` lives at the repo root.

```bash
# Run from source without installing
python -m yaas

# or, once installed in the environment
yaas
```

## Linting

CI runs flake8 the same way you can locally:

```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

## Cutting a release

Versioning is managed by [bumpver](https://github.com/mbarkhau/bumpver),
which keeps `pyproject.toml`, `src/yaas/__init__.py`, `README.md`, and
`inno_setup_script.iss` in sync.

```bash
git commit
bumpver update --patch   # or --minor / --major
uv build
uv publish
```

Pushing the version tag that `bumpver` creates triggers the release
workflows on GitHub Actions:

- `publish.yml` builds the sdist/wheel and publishes them to PyPI using
  [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (no API
  token needed).
- `release.yml` builds installers for Windows, macOS, and Linux and attaches
  them to the corresponding GitHub Release:
    - **Windows**: [PyInstaller](https://pyinstaller.org/) (`yaas.spec`) +
      [Inno Setup](https://jrsoftware.org/isinfo.php)
      (`inno_setup_script.iss`) → `yaas_installer.exe`.
    - **macOS**: PyInstaller + `hdiutil` → `yaas_installer.dmg` (unsigned).
    - **Linux**: PyInstaller + `appimagetool` → `yaas-x86_64.AppImage`
      (best-effort — this job is allowed to fail without blocking the rest
      of the release).

### Building installers locally

=== "Windows"

    ```powershell
    pyinstaller .\yaas.spec
    & 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' .\inno_setup_script.iss
    ```

=== "macOS"

    ```bash
    pyinstaller yaas.spec
    hdiutil create -volname Yaas -srcfolder dist/yaas.app -ov -format UDZO yaas_installer.dmg
    ```

=== "Linux (AppImage)"

    ```bash
    pyinstaller yaas.spec
    # Package dist/yaas/ into an AppDir, then:
    ./appimagetool-x86_64.AppImage AppDir yaas-x86_64.AppImage
    ```
