[app]

# (str) Title of your application
title = Склад Сырья

# (str) Package name
package.name = rawmaterialapp

# (str) Package domain (needed for android/ios packaging)
package.domain = org.test

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,db

# (str) Application versioning
version = 0.1

# (list) Application requirements
requirements = python3==3.11.0,kivy==2.3.0,sqlite3

android.api = 33
android.minapi = 21
android.ndk = 25b
# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = false, 1 = true)
warn_on_root = 1
p4a.branch = master
