#!/usr/bin/env python3
"""Android device profiles executed by the Aurora Code WS12 lab."""

ANDROID_PROFILES = {
  "phone": {
    "stageId": "android_real_mobile",
    "label": "Android phone AVD APK/PWA execution",
    "avdName": "AuroraCode_API36",
    "device": "pixel_6",
    "target": "android_avd",
  },
  "tablet": {
    "stageId": "android_real_tablet",
    "label": "Android tablet AVD APK/PWA execution",
    "avdName": "AuroraCodeTablet_API36",
    "device": "pixel_tablet",
    "target": "android_tablet_avd",
  },
}
