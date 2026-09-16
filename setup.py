from setuptools import setup

APP = ["run_live.py"]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/AppIcon.icns",
    "packages": ["connector", "mac_agent"],
    "plist": {
        "CFBundleName": "Muse Mac Connector",
        "CFBundleDisplayName": "Muse Mac Connector",
        "CFBundleIdentifier": "com.musemacconnector.app",
        "CFBundleShortVersionString": "0.4.2",
        "CFBundleVersion": "42",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    name="Muse Mac Connector",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
