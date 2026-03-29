def parse_incoming_packet(data: bytearray):
    data_bytes = list(data)

    if len(data_bytes) < 6:
        return None

    if data_bytes[:5] == [0x00, 0x01, 0x10, 0x00, 0x21]:
        scene = data_bytes[5]
        return {
            "cmd": "scene_activated",
            "scene": scene,
            "triggered": True,
        }

    if data_bytes[:5] == [0x00, 0x01, 0x10, 0x00, 0x16] and len(data_bytes) >= 7:
        addr = data_bytes[5]
        button = data_bytes[6]
        extra = data_bytes[7:]
        return {
            "cmd": "button_press",
            "address": addr,
            "button": button,
            "action": "release" if extra and not extra[0] else "press",
        }

    if (data_bytes[1:5] == [0x01, 0x10, 0x00, 0xC8] or data_bytes[1:5] == [0x01, 0x10, 0x00, 0x98]) and len(data_bytes) >= 8:
        addr = data_bytes[0]
        state = data_bytes[5]
        dim2 = data_bytes[7]
        return {
            "cmd": "dim",
            "address": addr,
            "state": state,
            "dim": dim2,
        }

    if data_bytes[1:5] == [0x01, 0x10, 0x00, 0x97] and len(data_bytes) >= 6:
        addr = data_bytes[0]
        state = data_bytes[5]
        return {
            "cmd": "change_state",
            "address": addr,
            "state": state,
        }

    if data_bytes[1:6] == [0x01, 0x10, 0x04, 0x20, 0x01] and len(data_bytes) >= 9 and data_bytes[6] == 0x11:
        addr = data_bytes[0]
        color_temp = int.from_bytes(data_bytes[7:], "big")
        return {
            "cmd": "color_temperature",
            "address": addr,
            "temperature": color_temp,
        }

    if data_bytes[1:6] == [0x01, 0x10, 0x04, 0x20, 0x03] and len(data_bytes) >= 10:
        addr = data_bytes[0]
        lightlevel = int.from_bytes(data_bytes[-2:], "big")
        return {
            "cmd": "motion",
            "address": addr,
            "lightlevel": lightlevel,
        }

    return None