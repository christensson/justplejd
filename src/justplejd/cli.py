import argparse
import asyncio
import json
import os
import sys

from . import commands
from .http_api import PlejdTraits, Site
from .plejd import Plejd


def parse_state(value: str):
    """Returns 'on', 'off' or an int 0-100 (dim level in percent)."""
    lowered = value.lower()
    if lowered in ("on", "off"):
        return lowered
    try:
        level = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid state '{value}': expected on, off or an integer 0-100")
    if not 0 <= level <= 100:
        raise argparse.ArgumentTypeError(f"invalid level {level}: must be between 0 and 100")
    return level


def parse_args():
    parser = argparse.ArgumentParser(
        prog="justplejd",
        description="Control Plejd devices.",
        epilog=(
            "examples:\n"
            "  justplejd                                  listen for events\n"
            "  justplejd --dump-devices devices.json      save devices (needs EMAIL/PASSWORD, optionally SITE_ID)\n"
            "  justplejd --devices devices.json           list devices and their state\n"
            "  justplejd --devices devices.json Ceiling on|off|0-100"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--devices", metavar="FILE", help="device file created with --dump-devices")
    parser.add_argument("--dump-devices", metavar="FILE", help="log in, write the site's devices to FILE and exit")
    parser.add_argument("name", nargs="?", help="device name (case-insensitive)")
    parser.add_argument("state", nargs="?", type=parse_state, help="on, off or a dim level 0-100")
    args = parser.parse_args()

    if args.dump_devices and (args.devices or args.name or args.state is not None):
        parser.error("--dump-devices cannot be combined with --devices, name or state")
    if args.devices and args.name is not None and args.state is None:
        parser.error("a state (on, off or 0-100) is required after the device name")
    if not args.devices and (args.name is not None or args.state is not None):
        parser.error("name and state require --devices FILE")
    return args


def get_credentials():
    # Read Plejd email and password from env variables:
    # EMAIL="your@email.com" PASSWORD="your-password" justplejd
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    site_id = os.environ.get("SITE_ID")

    if not email or not password:
        print("You need to provide the email and password to your Plejd account:")
        print("EMAIL=\"your@email.com\" PASSWORD=\"password\" justplejd")
        print('')
        print('This is only used to read your site configuration once during initialization and is not persisted.')
        sys.exit(1)

    return email, password, site_id


async def dump_devices(path: str):
    email, password, site_id = get_credentials()
    plejd = Plejd(email=email, password=password, site_id=site_id)
    error = await plejd._establish_site_connection()
    if error:
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(plejd.get_site().to_dict(), f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(plejd.get_site().devices)} devices to {path}")
    print("Note: the file contains your site's crypto key - keep it private.")


def find_device(site: Site, name: str):
    """Find a device by case-insensitive exact name, or else by unique name prefix."""
    room_titles = {r.id: r.title for r in site.rooms}

    def describe(d):
        return f"{d.title} (room={room_titles.get(d.room_id, '?')}, address={d.address})"

    wanted = name.casefold()
    matches = [d for d in site.devices if d.title.casefold() == wanted]
    if not matches:
        matches = [d for d in site.devices if d.title.casefold().startswith(wanted)]

    if len(matches) == 1:
        print(f"Matched device: {describe(matches[0])}")
        return matches[0]

    if not matches:
        print(f"No device matches '{name}'. Available devices:")
        candidates = site.devices
    else:
        print(f"'{name}' matches several devices, please be more specific:")
        candidates = matches
    for d in sorted(candidates, key=lambda d: d.title.casefold()):
        print(f"  * {describe(d)}")
    sys.exit(1)


TRAIT_NAMES = [
    (PlejdTraits.POWER, "power"),
    (PlejdTraits.DIM, "dim"),
    (PlejdTraits.TEMP, "color-temp"),
    (PlejdTraits.COVER, "cover"),
    (PlejdTraits.TILT, "tilt"),
    (PlejdTraits.GROUP, "group"),
]


def format_traits(traits: PlejdTraits):
    names = [name for flag, name in TRAIT_NAMES if flag in traits]
    unknown = int(traits) & ~sum(int(flag) for flag, _ in TRAIT_NAMES)
    if unknown:
        names.append(f"0x{unknown:x}")
    return ", ".join(names) or "-"


def format_state(device, states):
    if not device.has_power():
        return "-"
    state = states.get(device.address)
    if state is None:
        return "unknown"
    if not state["state"]:
        return "off"
    if PlejdTraits.DIM in device.traits:
        return f"on {round(state['dim'] * 100 / 255)}%"
    return "on"


async def list_devices(path: str):
    with open(path, encoding="utf-8") as f:
        site = Site.from_dict(json.load(f))

    plejd = Plejd(email=None, password=None, site=site)
    await plejd.connect()
    try:
        states = await plejd.get_states()
    finally:
        await plejd.disconnect()

    room_titles = {r.id: r.title for r in site.rooms}
    rows = [
        (d.title, room_titles.get(d.room_id, "?"), str(d.address), format_traits(d.traits), format_state(d, states))
        for d in sorted(site.devices, key=lambda d: (room_titles.get(d.room_id, ""), d.title.lower()))
    ]
    headers = ("NAME", "ROOM", "ADDRESS", "TRAITS", "STATE")
    widths = [max(len(r[i]) for r in rows + [headers]) for i in range(len(headers))]
    print('')
    for row in [headers] + rows:
        print("  ".join(col.ljust(w) for col, w in zip(row, widths)).rstrip())


async def set_state(path: str, name: str, state):
    with open(path, encoding="utf-8") as f:
        site = Site.from_dict(json.load(f))

    device = find_device(site, name)

    if state == "on":
        cmd = commands.turn_on(device.address)
    elif state == "off" or state == 0:
        cmd = commands.turn_off(device.address)
    else:
        if PlejdTraits.DIM not in device.traits:
            print(f"Warning: '{device.title}' does not seem to be dimmable")
        cmd = commands.dim(device.address, round(state * 255 / 100))

    plejd = Plejd(email=None, password=None, site=site)
    unsubscribe = plejd.on_change(print)
    await plejd.connect()
    try:
        print(f"Setting {device.title} (address={device.address}) to {state}")
        await plejd.run(cmd)
        # Give the command time to propagate and the mesh time to report back
        await asyncio.sleep(1)
    finally:
        unsubscribe()
        await plejd.disconnect()


async def listen():
    email, password, site_id = get_credentials()
    plejd = Plejd(email=email, password=password, site_id=site_id)

    # Listen to events coming in on the plejd mesh network
    unsubscribe = plejd.on_change(print)

    # Connect to closest connectible Plejd device
    await plejd.connect()

    try:
        # Wait indefinitely for on_change events
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        print("Exiting...")
    finally:
        unsubscribe()
        await plejd.disconnect()


async def _main(args):
    if args.dump_devices:
        await dump_devices(args.dump_devices)
    elif args.devices and args.name is None:
        await list_devices(args.devices)
    elif args.devices:
        await set_state(args.devices, args.name, args.state)
    else:
        await listen()


def main():
    args = parse_args()
    try:
        asyncio.run(_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
