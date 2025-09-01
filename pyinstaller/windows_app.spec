import importlib.metadata
import os
from datetime import datetime

from pyinstaller_versionfile import create_versionfile

import table_control

version = importlib.metadata.version("table-control")
meta = importlib.metadata.metadata("table-control")
filename = f"table-control-{version}.exe"
console = False
block_cipher = None
now = datetime.utcnow()

package_root = os.path.join(os.path.dirname(table_control.__file__))
package_icon = os.path.join(package_root, "assets", "icons", "table_control.ico")

version_info = os.path.join(os.getcwd(), "version_info.txt")

# Create windows version info
create_versionfile(
    output_file=version_info,
    version=f"{version}.0",
    company_name="MBI",
    file_description=meta.get("Summary", ""),
    internal_name="Table Control",
    legal_copyright=f"Copyright © {now.year} MBI. All rights reserved.",
    original_filename=filename,
    product_name="Table Control",
)

a = Analysis(
    ["entry_point.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        (os.path.join(package_root, "assets", "*.txt"), os.path.join("table_control", "assets")),
        (os.path.join(package_root, "assets", "icons", "*.ico"), os.path.join("table_control", "assets", "icons")),
        (os.path.join(package_root, "assets", "icons", "*.svg"), os.path.join("table_control", "assets", "icons")),
    ],
    hiddenimports=[
        "pyvisa",
        "pyvisa_py",
        "serial",
        "usb",
        "gpib_ctypes",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=filename,
    version=version_info,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    icon=package_icon,
)
