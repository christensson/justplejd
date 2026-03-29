def turn_off(device_addr: bytearray):
    # AA 0110 0097 00
    return [f"{device_addr:02x} 0110 0097 00"]

def turn_on(device_addr: bytearray):
    # AA 0110 0097 01
    return [f"{device_addr:02x} 0110 0097 01"]

def dim(device_addr: bytearray, dim: int):
    # AA 0110 0098 01 DDDD
    return [f"{device_addr:02x} 0110 0098 01 {dim:02x}{dim:02x}"]

def color_temperature(device_addr: bytearray, color_temp: int):
    # AA 0110 0420 030111 TTTT
    return [f"{device_addr:02x} 0110 0420 030111 {color_temp:04x}"]

def cover(device_addr: bytearray, cover: int):
    if cover < 0:
        # AA 0110 0420 030807 00
        return [f"{device_addr:02x} 0110 0420 030807 00"]
    else:
        # AA 0110 0420 030827 01 PPPP
        return [f"{device_addr:02x} 0110 0420 030827 01 {cover:04x}"]

def activate_scene(scene_index: int):
    # 02 0110 0021 II
    return [f"02 0110 0021 {scene_index:02x}"]