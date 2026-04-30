# -*- mode: python ; coding: utf-8 -*-
import os

project_root = SPECPATH  # PyInstaller sets this to the spec file's directory

a = Analysis(
    [os.path.join(project_root, 'web_server.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'templates'), 'templates'),
        (os.path.join(project_root, 'static'),   'static'),
        (os.path.join(project_root, 'src'),       'src'),
    ],
    hiddenimports=[
        'flask', 'flask.templating', 'flask.json',
        'jinja2', 'jinja2.ext',
        'werkzeug', 'werkzeug.serving', 'werkzeug.routing',
        'aiohttp', 'aiohttp.connector', 'aiohttp.client',
        'aiohttp.client_reqrep', 'aiohttp.streams',
        'aiosignal', 'frozenlist', 'multidict', 'yarl', 'attr', 'attrs',
        'psutil', 'psutil._psmacosx', 'psutil._psposix',
        'requests', 'requests.adapters', 'requests.packages',
        'urllib3', 'urllib3.util', 'urllib3.util.retry',
        'dotenv',
        'src.interface.web_app',
        'src.lcu.connector',
        'src.data.lolalytics_client',
        'src.data.manager',
        'src.data.aggregator',
        'src.engine',
        'src.scoring.scorer',
        'src.models',
    ],
    excludes=['pytest', 'hypothesis', 'riotwatcher'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DraftAdvisorServer',
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='DraftAdvisorServer',
)
