from enum import IntFlag
from typing import List
from aiohttp import ClientSession
from dataclasses import dataclass
from json import dumps

API_APP_ID = "zHtVqXt8k4yFyk2QGmgp48D9xZr2G94xWYnF4dak"
API_BASE_URL = "https://cloud.plejd.com"

headers = {
    "X-Parse-Application-Id": API_APP_ID,
    "Content-Type": "application/json",
}

class PlejdTraits(IntFlag):
    POWER = 0x8
    TEMP = 0x4
    DIM = 0x2
    GROUP = 0x1

    COVER = 0x10
    TILT = 0x40

@dataclass
class Scene:
    title: str
    id: str
    address: str
    def __init__(self, json, address):
        self.title = json['title']
        self.id = json['sceneId']
        self.address = address

@dataclass
class Room:
    title: str
    id: str

    def __init__(self, json):
        self.title = json['title']
        self.id = json['roomId']

    def to_dict(self):
        return {"id": self.id, "title": self.title}

    @classmethod
    def from_dict(cls, d):
        room = cls.__new__(cls)
        room.id = d['id']
        room.title = d['title']
        return room

@dataclass
class Device:
    title: str
    id: str
    address: str
    room_id: str
    traits: PlejdTraits

    def __init__(self, json, address: str):
        self.title = json.get('title', "Unknown")
        self.id = json['deviceId']
        self.room_id = json['roomId']
        self.traits = PlejdTraits(json['traits'])
        self.address = address
    
    def has_power(self):
        return PlejdTraits.POWER in self.traits

    def to_dict(self):
        return {
            "title": self.title,
            "id": self.id,
            "address": self.address,
            "room_id": self.room_id,
            "traits": int(self.traits),
        }

    @classmethod
    def from_dict(cls, d):
        device = cls.__new__(cls)
        device.title = d['title']
        device.id = d['id']
        device.address = d['address']
        device.room_id = d['room_id']
        device.traits = PlejdTraits(d['traits'])
        return device

@dataclass
class Site:
    id: str
    title: str
    crypto_key: str
    rooms: List[Room]
    devices: List[Device]
    scenes: List[Scene]

    def __init__(self, json):
        self.id = json['site']['siteId']
        self.title = json['site']['title']
        self.crypto_key = json['plejdMesh']['cryptoKey']

        self.rooms = []
        for r in json['rooms']:
            self.rooms.append(Room(r))

        self.scenes = []
        for s in json['scenes']:
            self.scenes.append(Scene(s, json['sceneIndex'][s['sceneId']]))

        self.devices = []
        for d in json['devices']:
            device_id = d['deviceId']
            device_address = json['deviceAddress'][device_id]
            self.devices.append(Device(d, device_address))

    def to_dict(self):
        room_titles = {r.id: r.title for r in self.rooms}
        return {
            "site_id": self.id,
            "title": self.title,
            "crypto_key": self.crypto_key,
            "rooms": [r.to_dict() for r in self.rooms],
            "devices": [
                {**d.to_dict(), "room": room_titles.get(d.room_id, "")}
                for d in self.devices
            ],
        }

    @classmethod
    def from_dict(cls, d):
        site = cls.__new__(cls)
        site.id = d['site_id']
        site.title = d['title']
        site.crypto_key = d['crypto_key']
        site.rooms = [Room.from_dict(r) for r in d.get('rooms', [])]
        site.devices = [Device.from_dict(dev) for dev in d['devices']]
        site.scenes = []
        return site
        
async def _get_session_token(session: ClientSession, username: str, password: str):
    resp = await session.post("/parse/login", json={"username": username, "password": password})
    if resp.status != 200:
        data = await resp.json()
        if data.get("code", 0) == 101:
            raise Exception("Invalid username/password")
        else:
            print("Failed to login to plejd. Not sure why")
            raise ConnectionError
    
    data = await resp.json()
    return data['sessionToken']

async def get_sites(username: str, password: str):
    async with ClientSession(base_url=API_BASE_URL, headers=headers) as session:
        session_token = await _get_session_token(session, username, password)
        session.headers["X-Parse-Session-Token"] = session_token
        resp = await session.post("/parse/functions/getSiteList", raise_for_status=True)
        json = await resp.json()
        sites_raw = json['result']
        sites: List[Site] = []
        for site in sites_raw:
            site_resp = await session.post("/parse/functions/getSiteById", params={"siteId": site['site']['siteId']})
            site_data = (await site_resp.json())['result'][0]
            sites.append(Site(site_data))
        
        return sites