# Building the APK in Google Colab

## Why it keeps failing with "N errors generated"

Every failed run compiled Kivy against **CPython 3.14** (look for
`include/python3.14` and `_PyLong_AsByteArray ... expected 6, have 5` in
the log). Kivy 2.3.0's C code does not build on Python 3.13/3.14.

There are **two** things that must both be in place:

1. `buildozer.spec` pins `requirements = python3==3.11.9,...`  ✅ (already set)
2. The **installed** `python-for-android` must be old enough to still know
   how to build CPython 3.11. A fresh `pip install buildozer` pulls the
   latest p4a, which defaults to 3.14 - so you must **downgrade it
   explicitly**, and then **delete the half-built target** so the change
   takes effect.

If you skip step 2 (or skip the clean), you get Python 3.14 again.

---

## The 4 cells - run every time, in order

### Cell 1 - project + system packages

```python
import os
# adjust if you uploaded/cloned somewhere else:
os.chdir('/content/RetirementTimeline_AndroidKit')
print(os.listdir())          # must list buildozer.spec and main.py

!sudo apt-get update -qq
!sudo apt-get install -y -qq \
    zip unzip openjdk-17-jdk \
    autoconf automake libtool libtool-bin pkg-config cmake patchelf \
    zlib1g-dev libncurses-dev libffi-dev libssl-dev \
    build-essential ccache libltdl-dev
```

### Cell 2 - PIN the toolchain (this is the step that gets skipped)

```python
# Force-downgrade. --force-reinstall so a newer p4a already present is replaced.
!pip install -q --force-reinstall \
    "buildozer==1.5.0" "python-for-android==2024.1.21" \
    "cython<3.1" "setuptools<74" "wheel"

# Verify BEFORE building - do not continue unless these match:
import importlib.metadata as md
print("buildozer          ", md.version("buildozer"))            # -> 1.5.0
print("python-for-android ", md.version("python-for-android"))   # -> 2024.1.21
import distutils; print("distutils OK")                          # must not raise
```

If `python-for-android` is not `2024.1.21`, restart the runtime
(`Runtime -> Restart session`) and run Cells 1-2 again before Cell 3.

### Cell 3 - wipe any half-built target from the previous attempt

```python
!rm -rf .buildozer/android/platform/build-* \
        .buildozer/android/platform/dists \
        .buildozer/android/platform/dist
```

### Cell 4 - build (25-40 min the first time)

```python
!buildozer -v android debug
```

Then, when `bin/*.apk` exists:

```python
from google.colab import files
import glob
apk = sorted(glob.glob('bin/*.apk'))[-1]
print("Built:", apk)
files.download(apk)
```

---

## Sanity check while it runs

Early in Cell 4's output you should see the python3 recipe fetching
**3.11.9**, e.g.:

```
[INFO]: Downloading python3 from https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
```

If you instead see `python3.13` / `python3.14` anywhere, stop - Cell 2 did
not take. Restart the runtime and redo Cells 1-4.

---

## If Cell 2 can't hold the pin (host Python too new for p4a 2024.1.21)

Build from a dedicated Python 3.11 venv instead:

```python
!sudo add-apt-repository -y ppa:deadsnakes/ppa
!sudo apt-get -qq install -y python3.11 python3.11-venv python3.11-dev
!python3.11 -m venv /content/p4a-venv
!/content/p4a-venv/bin/pip install -q "buildozer==1.5.0" \
    "python-for-android==2024.1.21" "cython<3.1"
!rm -rf .buildozer/android/platform/build-* .buildozer/android/platform/dists
!cd /content/RetirementTimeline_AndroidKit && \
    /content/p4a-venv/bin/buildozer -v android debug
```

---

## Faster / more reproducible: GitHub Actions

The workflow in `.github/workflows/android-build.yml` runs this exact
pinned toolchain on a Linux runner and caches the SDK/NDK, so repeat
builds take ~5 min. Push this folder to a repo and use the Actions tab.
