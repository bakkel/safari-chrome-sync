# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Safari ↔ Chrome Sync

Build with: pyinstaller safari_chrome_sync.spec
Output: dist/Safari Chrome Sync.app/
"""

block_cipher = None

a = Analysis(
    ['app_window.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6',
        'plistlib',
        'sqlite3',
        'uuid',
        'hashlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Safari Chrome Sync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Safari Chrome Sync',
)

app = BUNDLE(
    coll,
    name='Safari Chrome Sync.app',
    icon=None,
    bundle_identifier='com.safari-chrome-sync',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
    },
)
