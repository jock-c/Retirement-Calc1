[app]

# (str) Title of your application
title = Retirement Super Timeline

# (str) Package name
package.name = retirementtimeline

# (str) Package domain (needed for android/ios packaging)
package.domain = au.retirement.timeline

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf

# (list) Source files to exclude (let empty to not exclude anything)
source.exclude_exts = spec,txt,md

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests, bin, venv, .git, .github, __pycache__, .buildozer

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# python-for-android ships its own SDL2, so kivy_deps.* are NOT needed here.
#
# `python3` is a HARD PIN and must stay. Recent python-for-android
# defaults the target interpreter to CPython 3.13/3.14, and Kivy 2.3.0's
# Cython-generated C does not compile there (removed `Py_UNICODE`, changed
# `_PyLong_AsByteArray` signature) - you get "N errors generated" while
# building kivy. Pinning here forces p4a to build CPython 3.11.9 instead.
# Also install the matching toolchain before building (see colab_build.md /
# the GitHub workflow): buildozer==1.5.0 + python-for-android==2024.1.21.
requirements = python3,kivy==2.3.0,pyjnius

# (str) Supported orientation (one of landscape, sensorLandscape, portrait, sensorPortrait, all or sensor)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (list) Permissions
# ACTION_SEND (the share sheet) needs no permission. The storage
# permissions only help when writing the extra copy into /Download on
# older Android versions; harmless to request.
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 34

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (int) Android NDK API to use. This is the minimum API your app will support.
android.ndk_api = 24

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (list) The Android archs to build for.
# A single arch keeps the Colab build inside its session time limit.
# arm64-v8a covers essentially every phone from ~2019 onward. To also
# support old 32-bit devices, use:  arm64-v8a, armeabi-v7a
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) The format used to package the app for release mode (aab or apk or aar).
android.release_artifact = aab

# (str) The format used to package the app for debug mode (apk or aar).
android.debug_artifact = apk

#
# Python for android (p4a) specific
# p4a.branch = v2024.01.2

# (str) Bootstrap to use for android builds
p4a.bootstrap = sdl2
p4a.branch = v2024.01.21


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
# Colab runs as root; buildozer only warns, it still builds.
warn_on_root = 1
