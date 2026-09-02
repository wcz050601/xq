[app]
title = Python Chinese Chess
package.name = pyxq
package.domain = org.example
source.dir = .
source.include_exts = py,kv,png,jpg,wav,mp3,json
source.exclude_dirs = tests,.git,.venv,__pycache__
version = 0.1.0
requirements = python3,kivy,websockets
orientation = portrait
fullscreen = 0
android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 1

