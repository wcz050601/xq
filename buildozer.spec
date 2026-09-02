[app]
title = Python Chinese Chess
package.name = pyxq
package.domain = io.github.wcz050601

source.dir = .
source.include_exts = py,kv,png,jpg,wav,mp3,json
source.exclude_dirs = tests,.git,.venv,__pycache__

version = 0.1.0

requirements = python3,kivy,websockets

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.archs = arm64-v8a
android.accept_sdk_license = True

# 固定 Android 工具链
android.api = 36
android.minapi = 24
android.ndk = 28c

# 不使用不断变化的 p4a master
p4a.branch = v2026.05.09

[buildozer]
log_level = 2
warn_on_root = 1