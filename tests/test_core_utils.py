from table_control.core import utils


def test_get_resource_name():
    assert utils.get_resource_name("") == ""
    assert utils.get_resource_name("8") == "GPIB0::8::INSTR"
    assert utils.get_resource_name("127.0.0.1:4000") == "TCPIP0::127.0.0.1::4000::SOCKET"
    assert utils.get_resource_name("localhost:4000") == "TCPIP0::localhost::4000::SOCKET"
    assert utils.get_resource_name("COM8") == "ASRL8::INSTR"
    assert utils.get_resource_name("ASRL8") == "ASRL8::INSTR"
    assert utils.get_resource_name("TCPIP0::localhost::4000::SOCKET") == "TCPIP0::localhost::4000::SOCKET"


def test_get_pyvisa_library():
    assert utils.get_visa_library("") == ""
    assert utils.get_visa_library("ASRL") == "@py"
    assert utils.get_visa_library("USB") == "@py"
    assert utils.get_visa_library("TCPIP") == "@py"
    assert utils.get_visa_library("GPIB") == ""
