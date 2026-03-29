import asyncio
import os

from typing import Any, Callable, List
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice

from . import http_api
from .packet_parser import parse_incoming_packet
from .proto import create_auth_response, encode_payloads, encrypt_decrypt, extract_mac_address

DATA_SENDING_UUID = "31ba0004-6085-4726-be45-040c957391b5"
DATA_RETRIEVAL_UUID = "31ba0005-6085-4726-be45-040c957391b5"
AUTH_UUID = "31ba0009-6085-4726-be45-040c957391b5"
PING_UUID = "31ba000a-6085-4726-be45-040c957391b5"

class PlejdDevice():
    def __init__(self, device: BLEDevice, mac_address: str, rssi: int):
        self.device = device
        self.mac_address = mac_address
        self.rssi = rssi

class Plejd():
    def __init__(self, email: str, password: str, site_id = '', crypto_key  = ''):
        if not crypto_key and not (email or password):
            print("You need to provide the email and password to your Plejd account. The information will only be used to retrieve a secret key from the official Plejd API which is needed to communicate with your Plejd devices. You do that by running Plejd(email='foo@bar.com', password='s3cret')")

        self._email = email
        self._password = password
        self._site_id = site_id
        self._crypto_key = crypto_key
        asyncio.get_event_loop().call_soon(asyncio.create_task, self._healthcheck())
        self._on_change_callbacks = []
        self._is_connected = False
        self._client = None
        self._site = None

    async def connect(self, timeout = 3.0):
        error = await self._establish_site_connection()
        if error:
            raise Exception(error)

        did_connect = False
        while not did_connect:
            did_connect = await self._connect(timeout)

            if not did_connect:
                await self.disconnect()
    
    async def disconnect(self):
        if self._is_connected or not self._client or not self._client.is_connected:
            return
        self._is_connected = False

        try:
            await self._client.stop_notify(DATA_RETRIEVAL_UUID)
        except:
            pass

        try:
            await self._client.disconnect()
        except Exception as e:
            print(f"Failed disconnecting... {e}")

    async def run(self, payloads):
        encoded_payloads = encode_payloads(self._crypto_key, self.gateway.mac_address, payloads)
        for payload in encoded_payloads:
            try:
                await self._client.write_gatt_char(DATA_SENDING_UUID, bytearray(payload))
            except Exception as e:
                if str(e) == "In Progress":
                    asyncio.get_event_loop().call_later(1, lambda: asyncio.create_task(self.run(payloads)))
                    print("Command already in progress. Will retry soon")
                    return
                
                async def reconnect_and_retry():
                    await self._reconnect()
                    if self._client.is_connected:
                        await self.run(payloads)
                
                asyncio.get_event_loop().call_later(self.connection_timeout, lambda: asyncio.create_task(reconnect_and_retry()))
    
    def on_change(self, callback: Callable[[Any], None]) -> Callable[[], None]:
        self._on_change_callbacks.append(callback)

        def unsubscribe() -> None:
            try:
                self._on_change_callbacks.remove(callback)
            except ValueError:
                pass  # Already removed or never registered

        return unsubscribe

    def get_site(self):
        return self._site
    
    async def _establish_site_connection(self):
        if self._crypto_key:
            return None
        
        sites = await http_api.get_sites(self._email, self._password)
        if len(sites) >= 2 and not self._site_id:
            print("You have more than two sites, and I need to know which one you want to control. Do so by providing the site_id: Plejd(email='foo@bar.com', password='s3cret', site_id='00000000-0000-0000-0000-000000000000')")
            self._print_site_info(sites)
            print('')
            return 'multiple_sites'
        
        matching_site = next((site for site in sites if site.id == self._site_id), None)
        if not matching_site:
            print(f"You provided a site ID ({self._site_id}) - But I can't seem to find that site on your account.")
            print('')
            self._print_site_info(sites)
            print('')
            return 'invalid_site_id'
        
        self._crypto_key = matching_site.crypto_key
        self._site = matching_site

        print(f"Will connect to {matching_site.title} with {len(matching_site.rooms)} room{'' if len(matching_site.rooms) == 1 else 's'}:")
        for room in matching_site.rooms:
            devices = [d for d in matching_site.devices if d.room_id == room.id]
            print(f"> {room.title}")
            for d in devices:
                print(f"  * {d.title} (address={d.address})")

        print('')

        return None

    def _print_site_info(self, sites: List[http_api.Site]):
        print("These were the sites I found:")
        for site in sites:
            print(f"> {site.title} ({len(site.devices)} device{'' if len(site.devices) == 1 else 's'}, site id {site.id})")
        
    async def _connect(self, timeout):
        self.gateway = await self._discover_gateway(timeout)

        if not self.gateway:
            return False
        
        self._is_connected = False
        self._client = BleakClient(self.gateway.device.address)
        print("Connecting...")
        await self._client.connect()
        self._is_connected = self._client.is_connected

        did_auth = await self._authenticate()
        if did_auth:
            print("Authed successfully!")
        else:
            print("Failed to connect: Could not authenticate. Retrying...")
            self._is_connected = False
            return False

        await self._client.start_notify(DATA_RETRIEVAL_UUID, self._received_data)
        print("Ready!")

        return True
    
    async def _reconnect(self):
        await self.disconnect()
        await self.connect()

    async def _healthcheck(self):
        while True:
            await asyncio.sleep(5)
            if not self._client or not self._client.is_connected or not self._is_connected:
                continue
            try:
                await self._ping()
            except Exception as e:
                print(f"Healthcheck failed. Reconnecting...")
                await self._reconnect()

    async def _discover_gateway(self, timeout: float):
        print("Scanning for plejd output devices to connect to...")

        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

        if not devices:
            print("Failed to find gateway device: No BT devices found.")
            return None

        plejd_devices: List[PlejdDevice] = []
        gateway_candidates = set(map(lambda d: d.id, filter(lambda d: d.has_power(), self._site.devices)))
        for device, adv in devices.values():
            if adv.local_name and adv.local_name.startswith("P mesh"):
                mdata = adv.manufacturer_data.get(887)
                mac_address = extract_mac_address(mdata)
                if mac_address and mac_address.replace(':', '') in gateway_candidates:
                    plejd_devices.append(PlejdDevice(device, mac_address, adv.rssi))
        
        # Sort them by signal strength
        plejd_devices = sorted(plejd_devices, key=lambda x: -x.rssi)
        if len(plejd_devices) == 0:
            print("Failed to find gateway device: No Plejd devices found nearby.")
            return None
        
        print(f"Found {len(plejd_devices)} plejd devices nearby. Picked the one with strongest signal ({self._get_device_name(plejd_devices[0].mac_address)}) as gateway.")

        return plejd_devices[0]

    async def _authenticate(self):
        print('Authenticating...')
        await self._client.write_gatt_char(AUTH_UUID, b'\x00')
        await asyncio.sleep(1) # Wait for the challenge to be generated. Sure there's a better way to do this, but can't wait for the ACK (write-without-response)
        challenge = await self._client.read_gatt_char(AUTH_UUID)
        auth_response = create_auth_response(challenge, self._crypto_key)
        await self._client.write_gatt_char(AUTH_UUID, auth_response)

        return await self._ping()

    async def _ping(self):
        ping = bytearray(os.urandom(1))
        await self._client.write_gatt_char(PING_UUID, ping)
        pong = await self._client.read_gatt_char(PING_UUID)
        return ((ping[0] + 1) & 0xFF) == pong[0]

    async def _received_data(self, _char, data: bytearray):
        data = encrypt_decrypt(self._crypto_key, self.gateway.mac_address, data)
        event = parse_incoming_packet(data)
        if event is None:
            return
        for cb in self._on_change_callbacks:
            cb(event)

    def _get_device_name(self, mac_address: str):
        if not self._site:
            return mac_address
        
        formatted_addr = mac_address.replace(':', '')
        device = next((d for d in self._site.devices if d.id == formatted_addr), None)
        if not device:
            return mac_address

        return device.title