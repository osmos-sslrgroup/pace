# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(50000)

from PyInstaller.utils.hooks import collect_all

datas = [('ui_ux_design', 'ui_ux_design')]
binaries = []
hiddenimports = []

# Collect all data files, binaries, and hidden imports for phreeqpython
tmp_ret = collect_all('phreeqpython')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]



a = Analysis(
    ['backend/run_desktop.py'],
    pathex=['backend'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio', 'tensorflow', 'tensorboard',
        'tf_keras', 'keras', 'dask', 'distributed', 'catboost', 'xgboost',
        'IPython', 'jupyter', 'zmq', 'bokeh', 'altair', 'sympy', 'sklearn',
        'scipy', 'statsmodels', 'confluent_kafka', 'docker', 'pytest'
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PACE_Permionics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, # Keep console true to see logs during startup and to close server easily
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
