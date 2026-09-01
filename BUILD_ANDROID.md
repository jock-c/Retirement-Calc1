# Building the Android app (Retirement Super Timeline)

This folder turns the same Kivy code that powers the Windows `.exe` into
an Android app, using **Buildozer** (which drives python-for-android).

| File | Purpose |
|---|---|
| `main.py` | The application (Android-adapted copy of `retirement_timeline_app.py`) |
| `buildozer.spec` | Buildozer / python-for-android build configuration |
| `requirements-dev.txt` | Packages to run/test `main.py` on a PC before packaging |
| `colab_build.md` | Copy-paste cells for building in Google Colab |
| `.github/workflows/android-build.yml` | Cloud build of a debug APK on GitHub Actions |

## What changed from the desktop version

* Removed the `from kivy_deps import sdl2, glew` imports (Windows-desktop
  only; python-for-android bundles its own SDL2).
* Entry point renamed to `main.py` (Buildozer requires this name).
* **"Print"** button is now **"Save / Share"**: on Android it saves a
  `.txt` copy into the app folder (and, best effort, into `Download/`) and
  opens the system share sheet. On a PC the original "send to default
  printer" behaviour is kept, so `python main.py` still works for testing.
* Soft-keyboard handling (`Window.softinput_mode`) so fields aren't hidden
  while typing.

The retirement calculation logic is byte-for-byte the same.

---

## Important build settings

### The target Python must be 3.11 - two things enforce it

1. `buildozer.spec` hard-pins `requirements = python3==3.11.9,...`
2. Install the matching toolchain and wipe stale build dirs, because a
   fresh `pip install buildozer` pulls the newest python-for-android
   (defaults to CPython 3.13/3.14):

   ```bash
   pip install --force-reinstall "buildozer==1.5.0" \
       "python-for-android==2024.1.21" "cython<3.1" "setuptools<74"
   rm -rf .buildozer/android/platform/build-* .buildozer/android/platform/dists
   ```

Kivy 2.3.0's Cython-generated C does not compile on Python 3.13/3.14
(removed `Py_UNICODE`, changed `_PyLong_AsByteArray` signature):

```
kivy/graphics/... 'Py_UNICODE' is deprecated
... error: too few arguments to function call, expected 6, have 5
N errors generated.
# Command failed: ... pythonforandroid.toolchain create ...
```

Full Colab steps: `colab_build.md`.  GitHub Actions:
`.github/workflows/android-build.yml` (already pinned).

### Buildozer needs Linux

Buildozer **cannot build on native Windows or macOS**. Pick one of:

1. **GitHub Actions** (no local setup) - recommended, and caches the SDK/NDK
2. **Google Colab** - see `colab_build.md`
3. **WSL 2 (Ubuntu) on Windows**
4. **Docker on any OS**

---

## Option 1 - GitHub Actions

The workflow runs on `ubuntu-latest` and installs the **pinned toolchain**
(`buildozer==1.5.0`, `python-for-android==2024.1.21`, `cython<3.1`), then
caches the Android SDK/NDK so later runs take ~5 min.

1. Push **the contents of this folder** as a repo root (so `buildozer.spec`
   and `main.py` are at the top level):

   ```bash
   cd RetirementTimeline_AndroidKit
   git init
   git add .
   git commit -m "Retirement Super Timeline - Android"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```

2. **Actions** tab -> the **Build Android APK** workflow runs on push
   (or click **Run workflow**).

3. When it finishes (~20-30 min first time), download the
   **`retirement-timeline-apk`** artifact -
   `retirementtimeline-1.0.0-<arch>-debug.apk`.

4. Copy the APK to your phone and open it. Allow "install unknown apps"
   for your file manager / browser the first time.

The debug APK is self-signed - fine for personal use. For the Play Store
you need `buildozer android release` and your own signing keystore.

---

## Option 2 - Google Colab

See **`colab_build.md`** for the exact cells. Key point: after any failed
run, delete `.buildozer/android/platform/build-*` before rebuilding so the
Python 3.11 pin takes effect.

---

## Option 3 - WSL 2 (Windows)

1. Install WSL + Ubuntu (PowerShell as admin, then reboot):

   ```powershell
   wsl --install -d Ubuntu-22.04
   ```

2. Install the toolchain in the Ubuntu shell:

   ```bash
   sudo apt update
   sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
     autoconf automake libtool libtool-bin pkg-config zlib1g-dev \
     libncurses-dev libffi-dev libssl-dev build-essential ccache libltdl-dev
   pip3 install --user "buildozer==1.5.0" "python-for-android==2024.1.21" "cython<3.1"
   echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc && source ~/.bashrc
   ```

3. Copy this folder into the Linux filesystem (building on `/mnt/c` is
   slow and hits permission errors):

   ```bash
   cp -r "/mnt/c/Users/<you>/.../RetirementTimeline_AndroidKit" ~/rt-android
   cd ~/rt-android
   buildozer android debug
   ```

4. Install onto a USB-connected phone (USB debugging on):

   ```bash
   buildozer android deploy run
   ```

---

## Option 4 - Docker (any OS)

The `:latest` image ships a too-new p4a. Pin inside the container:

```bash
cd RetirementTimeline_AndroidKit
docker run --rm -v "$PWD":/home/user/hostcwd --entrypoint bash kivy/buildozer:latest -c \
  "pip install --user 'buildozer==1.5.0' 'python-for-android==2024.1.21' 'cython<3.1' && \
   ~/.local/bin/buildozer android debug"
```

APK appears in `bin/`. (Windows PowerShell: use `${PWD}`.)

---

## Test on the desktop first

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

---

## Troubleshooting

* **`5 errors generated` / `Py_UNICODE is deprecated` while Cythonizing
  kivy** - a too-new python-for-android built CPython 3.13/3.14. Confirm
  `buildozer --version` is 1.5.0 and `pip show python-for-android` is
  2024.1.21, then `rm -rf .buildozer/android/platform/build-*` and
  rebuild. As a fallback set `requirements =
  python3==3.11.9,kivy==2.3.0,pyjnius` in `buildozer.spec`.
* **`buildozer --version` shows something other than 1.5.0** - another
  buildozer is ahead on `PATH`. `pip uninstall -y buildozer` then
  `pip install buildozer==1.5.0`.
* **`Aidl not found` / SDK license** - `buildozer.spec` sets
  `android.accept_sdk_license = True`; if it still stalls locally, run
  `buildozer android debug` once interactively and accept the prompt.
* **Build fails on `/mnt/c/...` under WSL** - copy the project into `~`
  and build there.
* **App installs but crashes on launch** - `buildozer android logcat`
  (or `adb logcat | grep -i python`) shows the Python traceback.
* **Icon / splash** - add PNGs and set `icon.filename` /
  `presplash.filename` in `buildozer.spec`.
* **Emoji in section headers show as boxes on the phone** - cosmetic only,
  not a build error. Kivy's bundled Roboto font has no pictographic
  glyphs. Either delete the leading emoji from the `SectionLabel(text=...)`
  calls in `main.py`, or bundle an emoji-capable `.ttf` and set it as the
  Kivy default font. The check marks / warning triangle / box-drawing
  lines in the results panel do render.
* **Rename app / package id** - edit `title`, `package.name`,
  `package.domain` before the first release (changing `package.domain`
  later makes it a different app).
