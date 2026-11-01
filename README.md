# Just Plejd - A plejd Python API

Control your Plejd devices from Python! This package lets you connect to your Plejd setup, list rooms/scenes/devices, listen to changes, and perhaps most importantly - send commands to your devices.

## ⚡️ Installation

```
git clone https://github.com/peterssonjesper/justplejd.git
cd justplejd
pip install .
```

## 🚀 Example

Below is an example of how to use it:

```python
import asyncio
from justplejd import Plejd, commands

async def main():
    plejd = Plejd(email='your@email.com', password='your-password')
    await plejd.connect()

    # Listen to events coming in on the plejd mesh network
    unsubscribe = plejd.on_change(print)

    # Run comands to control lights, activates scenes, etc.
    await plejd.run(commands.turn_on(39))  # Replace 39 with your device address
    await plejd.run(commands.turn_off(39))
    await plejd.run(commands.dim(39, 182)) # 182 being a number between 0 (off) to 255 (on)
    await plejd.run(commands.activate_scene(1)) # 1 being the scene address

    try:
        # Wait indefinitely for on_change events
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        print("Exiting...")
    finally:
        unsubscribe()
        await plejd.disconnect()

asyncio.run(main())
```

### Then run it

```bash
EMAIL="your@email.com" PASSWORD="your-plejd-password" python example.py
```

### Command line usage

There is also a small command line tool, `justplejd` (installed with the package, or run with `poetry run justplejd` from a checkout). First dump your site's devices to a file (this is the only step that needs your Plejd credentials; add `SITE_ID=...` if you have several sites):

```bash
EMAIL="your@email.com" PASSWORD="your-plejd-password" justplejd --dump-devices devices.json
```

List the devices and their current state:

```bash
justplejd --devices devices.json
```

Control a device by name. `STATE` is `on`, `off` or a dim level from `0` to `100`:

```bash
justplejd --devices devices.json "Ceiling" on
justplejd --devices devices.json "Ceiling" 40
justplejd --devices devices.json "Ceiling" off
```

The devices file contains your site's crypto key, so keep it private.

## 🙏 Credits & Inspiration

Big shoutout to [PyPlejd](https://github.com/thomasloven/pyplejd) - a lot of this project is inspired (okay, also borrowed) from their excellent work.

The main innovation here is simply just a workaround to extract the Plejd device's MAC address directly from its Bluetooth advertisement. This makes it possible to run the library on macOS and iOS, where traditional access to Bluetooth MAC addresses is restricted due to system-level obfuscation.
