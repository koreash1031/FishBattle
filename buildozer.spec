[app]
title = Fish Battle
package.name = fishbattle
package.domain = com.fishbattle
source.dir = web_build
source.include_exts = py,png,jpg,jpeg,md,json
source.include_patterns = data/*.md
version = 0.1.0
requirements = python3,pygame
orientation = portrait
fullscreen = 1
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
