import asyncio
from justplejd import Plejd, commands
import os

async def main():
    # Read Plejd email and password from env variables, so we can run the example with
    # EMAIL="your@email.com" PASSWORD="your-password" python example.py
    email = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    site_id = os.environ.get("SITE_ID")

    if not email or not password:
        print("You need to provide the email and password to your Plejd account:")
        print("EMAIL=\"your@email.com\" PASSWORD=\"password\" python example.py")
        print('')
        print('This is only used to read your site configuration once during initialization and is not persisted.')
        exit(1)

    plejd = Plejd(email=email, password=password, site_id=site_id)

    # Listen to events coming in on the plejd mesh network
    unsubscribe = plejd.on_change(print)

    # Connect to closest connectible Plejd device
    await plejd.connect()

    # Run comands to control lights, activates scenes, etc.
    # await plejd.run(commands.turn_on(39))  # Replace 39 with your device address
    # await plejd.run(commands.turn_off(39))
    # await plejd.run(commands.dim(39, 182)) # 182 being a number between 0 (off) to 255 (on)
    # await plejd.run(commands.activate_scene(1)) # 1 being the scene address

    try:
        # Wait indefinitely for on_change events
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        print("Exiting...")
    finally:
        unsubscribe()
        await plejd.disconnect()

asyncio.run(main())