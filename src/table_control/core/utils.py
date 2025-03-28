import re


def get_resource_name(resource_name: str) -> str:
    """Create valid VISA resource name for short descriptors."""
    m = re.match(r"^(\d+)$", resource_name)
    if m:
        resource_name = f"GPIB0::{m.group(1)}::INSTR"

    m = re.match(r"^(\d+\.\d+\.\d+\.\d+)\:(\d+)$", resource_name)
    if m:
        resource_name = f"TCPIP0::{m.group(1)}::{m.group(2)}::SOCKET"

    m = re.match(r"^(\w+)\:(\d+)$", resource_name)
    if m:
        resource_name = f"TCPIP0::{m.group(1)}::{m.group(2)}::SOCKET"

    return resource_name


def get_visa_library(resource_name: str) -> str:
    """Deduce VISA library from resource name."""
    visa_library = ""

    if resource_name.startswith("TCPIP"):
        visa_library = "@py"

    if resource_name.startswith("USB"):
        visa_library = "@py"

    return visa_library
