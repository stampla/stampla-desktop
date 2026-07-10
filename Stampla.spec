# PyInstaller build for the macOS app bundle.
# Build with: pyinstaller --noconfirm Stampla.spec

a = Analysis(
    ["src/stampla_desktop/__main__.py"],
    datas=[("src/stampla_desktop/resources", "stampla_desktop/resources")],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Stampla",
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Stampla",
)

app = BUNDLE(
    coll,
    name="Stampla.app",
    icon="assets/icon.icns",
    bundle_identifier="org.stampla.desktop",
    info_plist={
        "CFBundleDisplayName": "Stampla",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
)
