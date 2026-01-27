import re


def get_resource_name(resource_name: str) -> str:
    """Create valid VISA resource name for short descriptors."""
    m = re.match(r"^(\d+)$", resource_name)
    if m:
        return f"GPIB0::{m.group(1)}::INSTR"

    m = re.match(r"^COM(\d+)$", resource_name)
    if m:
        return f"ASRL{m.group(1)}::INSTR"

    m = re.match(r"^ASRL(\d+)$", resource_name)
    if m:
        return f"ASRL{m.group(1)}::INSTR"

    m = re.match(r"^(\d+\.\d+\.\d+\.\d+)\:(\d+)$", resource_name)
    if m:
        return f"TCPIP0::{m.group(1)}::{m.group(2)}::SOCKET"

    m = re.match(r"^(\w+)\:(\d+)$", resource_name)
    if m:
        return f"TCPIP0::{m.group(1)}::{m.group(2)}::SOCKET"

    return resource_name


def get_visa_library(resource_name: str) -> str:
    """Deduce VISA library from resource name."""
    visa_library = ""

    if resource_name.startswith(("ASRL", "USB", "TCPIP")):
        visa_library = "@py"

    return visa_library


def is_serial_resource(resource_name: str) -> bool:
    s = resource_name.strip().upper()
    return s.startswith("ASRL") or s.startswith("COM")
