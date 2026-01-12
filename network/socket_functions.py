from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
  from utils.orbis import PfsSKKey

import asyncio
import orjson

from network.exceptions import SocketError
from utils.constants import IP, PORT_CECIE, logger

class SocketPS:
    """Async functions to mainly interact with cecie."""
    def __init__(self, host: str, port: int, maxConnections: int = 16) -> None:
        self.host = host
        self.port = port
        self.semaphore = asyncio.Semaphore(maxConnections) # Maximum 16 mounts at once
        self.semaphore_alt = asyncio.Semaphore(maxConnections) # For operations that does not need a mount slot
    SUCCESS = "srOk"
    async def send_tcp_message_with_response(self, message: bytes, semaphore: asyncio.Semaphore, deserialize: bool = True) -> str | bytes:
        writer = None
        try:
            async with semaphore:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                writer.write(message)
                await writer.drain()

                response = await reader.read(1024)

                logger.info(response)
                if deserialize:
                    response = orjson.loads(response)
                return response

        except OSError as e:
            logger.error(f"An error occured while sending tcp message (Cecie): {e}")
            raise SocketError("Error communicating with socket.")

        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()

    async def test_connection(self) -> None:
        writer = None
        try:
            async with self.semaphore_alt:
                _, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), timeout=10)
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()

    async def socket_dump(self, folder: str, savename: str) -> None: 
        request = orjson.dumps({
            "RequestType": "rtDumpSave",
            "dump": {
                "saveName": savename,
                "targetFolder": folder,
                "selectOnly": []
                }
            }) + b"\r\n"

        response = await self.send_tcp_message_with_response(request, self.semaphore)

        if response.get("ResponseType") != self.SUCCESS:
            raise SocketError(response.get("code", "Failed to dump save!"))

    async def socket_update(self, folder: str, savename: str) -> None: 
        message = orjson.dumps({
            "RequestType": "rtUpdateSave",
            "update": {
                "saveName": savename,
                "sourceFolder": folder,
                "selectOnly": []
            }
        }) + b"\r\n"

        response = await self.send_tcp_message_with_response(message, self.semaphore)

        if response.get("ResponseType") != self.SUCCESS:
            raise SocketError(response.get("code", "Failed to update save!"))

    async def socket_keyset(self) -> int:
        message = orjson.dumps({
            "RequestType": "rtKeySet"
        }) + b"\r\n"

        response = await self.send_tcp_message_with_response(message, self.semaphore_alt)

        return response.get("keyset", "FAIL!")

    async def socket_createsave(self, folder: str, savename: str, blocks: int) -> None:
        message = orjson.dumps({
            "RequestType": "rtCreateSave",
            "create": {
                "saveName": savename,
                "sourceFolder": folder,
                "blocks": blocks
                }
        }) + b"\r\n"

        response = await self.send_tcp_message_with_response(message, self.semaphore)

        if response.get("ResponseType") != self.SUCCESS:
            raise SocketError(response.get("code", "Failed to create a save!"))

    async def socket_decryptsdkey(self, sealed_key: PfsSKKey) -> None:
        message = orjson.dumps({
            "RequestType": "rtDecryptSealedKey",
            "decsdkey": {
                "sealedKey": sealed_key.as_array()
            }
        }) + b"\r\n"

        response = await self.send_tcp_message_with_response(message, self.semaphore_alt)

        if response.get("ResponseType") == "srInvalid":
            raise SocketError("Failed to decrypt sealed key!")

        sealed_key.dec_key.extend(orjson.loads(response["json"]))

C1socket = SocketPS(IP, PORT_CECIE)
