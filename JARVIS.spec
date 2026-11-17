from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH)
hidden = (
    ["piper", "piper.voice", "piper.config", "piper.espeakbridge"]
    + collect_submodules("faster_whisper")
    + collect_submodules("cv2")
    + ["jarvis.rosto", "jarvis.ouvinte", "jarvis.fala", "jarvis.locutores",
       "jarvis.ambiente", "jarvis.narrador"]
)

a = Analysis(
    [str(ROOT / "jarvis_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "jarvis" / "interface"), "jarvis/interface"),
        (str(ROOT / "jarvis" / "config.json"), "jarvis"),
        (str(ROOT / "skills"), "skills"),
        (str(ROOT / "modelos" / "piper"), "modelos/piper"),
        (str(ROOT / "modelos" / "locutor"), "modelos/locutor"),
        (str(ROOT / "modelos" / "rosto"), "modelos/rosto"),
        (str(ROOT / "assets" / "jarvis.ico"), "assets"),
    ],
    hiddenimports=hidden + ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "assets" / "jarvis.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JARVIS",
)
