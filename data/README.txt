Put the launcher icon here as:  icon.png

Requirements:
  - PNG format
  - square (same width and height); 512x512 is ideal
buildozer / python-for-android generate every density + the adaptive
icon from this one file. buildozer.spec points at it via:
  icon.filename = %(source.dir)s/data/icon.png

To make icon.png from a photo on Windows, see make_icon.ps1 in the
parent folder (RetirementTimeline_AndroidKit).
