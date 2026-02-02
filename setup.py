"""
Vox - AI-powered text rewriting through macOS contextual menu

Setup script for building with py2app.
"""
from setuptools import setup

APP = ["main.py"]
DATA_FILES = []
OPTIONS = {
    "py2app": {
        "argv_emulation": False,
        "strip": False,
        "arch": None,
        "plist": {
            "CFBundleName": "Vox",
            "CFBundleDisplayName": "Vox",
            "CFBundleIdentifier": "com.voxapp.rewrite",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSUIElement": True,
            "NSServices": [
                {
                    "NSMessage": "fixGrammarService",
                    "NSMenuItem": {"default": "Rewrite with Vox"},
                    "NSPortName": {"default": "Vox"},
                    "NSSendTypes": ["public.utf8-plain-text"],
                    "NSRestrictedContext": True,
                },
                {
                    "NSMessage": "fixGrammarService",
                    "NSMenuItem": {"default": "Rewrite with Vox/Fix Grammar"},
                    "NSPortName": {"default": "Vox"},
                    "NSSendTypes": ["public.utf8-plain-text"],
                },
                {
                    "NSMessage": "professionalService",
                    "NSMenuItem": {"default": "Rewrite with Vox/Professional"},
                    "NSPortName": {"default": "Vox"},
                    "NSSendTypes": ["public.utf8-plain-text"],
                },
                {
                    "NSMessage": "conciseService",
                    "NSMenuItem": {"default": "Rewrite with Vox/Concise"},
                    "NSPortName": {"default": "Vox"},
                    "NSSendTypes": ["public.utf8-plain-text"],
                },
                {
                    "NSMessage": "friendlyService",
                    "NSMenuItem": {"default": "Rewrite with Vox/Friendly"},
                    "NSPortName": {"default": "Vox"},
                    "NSSendTypes": ["public.utf8-plain-text"],
                },
            ],
        },
        "includes": [
            "vox",
            "vox.service",
            "vox.api",
            "vox.config",
            "vox.ui",
            "vox.notifications",
        ],
        "excludes": ["pkg_resources"],
        "packages": ["vox"],
    }
}

setup(
    name="Vox",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS["py2app"]},
)
