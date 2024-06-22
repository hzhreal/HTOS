from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
  from utils.orbis import PfsSKKey

import asyncio
import json
from utils.constants import logger

class SocketError(Exception):
  """Exception raised for errors relating to the socket."""
  def __init__(self, message: str) -> None:
    self.message = message

class SocketPS:
  """Async functions to mainly interact with cecie."""
  def __init__(self, HOST: str, PORT: int, maxConnections: int = 16) -> None:
    self.HOST = HOST
    self.PORT = PORT
    self.semaphore = asyncio.Semaphore(maxConnections) # Maximum 16 mounts at once
  SUCCESS = "srOk"
  async def send_tcp_message_with_response(self, message: str, deserialize: bool = True) -> str | bytes:
    writer = None
    try:
      async with self.semaphore:
        reader, writer = await asyncio.open_connection(self.HOST, self.PORT)
        writer.write(message.encode("utf-8"))
        await writer.drain()
      
        response = await reader.read(1024)

        logger.info(response)
        if deserialize:
          response = json.loads(response)
        return response
    
    except (ConnectionError, asyncio.TimeoutError) as e:
      logger.error(f"An error occured while sending tcp message (Cecie): {e}")
      raise SocketError("Error communicating with socket.")
    
    finally:
      if writer is not None:
        writer.close()
        await writer.wait_closed()
      
  async def testConnection(self) -> None:
    _, writer = await asyncio.wait_for(asyncio.open_connection(self.HOST, self.PORT), timeout=10)
    writer.close()
    await writer.wait_closed()

  async def socket_dump(self, folder: str, savename: str) -> None: 
    request = json.dumps({
      "RequestType": "rtDumpSave", 
      "dump": {
        "saveName": savename, 
        "targetFolder": folder, 
        "selectOnly": []
      }
    }) + "\r\n"

    response = await self.send_tcp_message_with_response(request)
    
    if response.get("ResponseType") != self.SUCCESS:
      raise SocketError(response.get("code", "Failed to dump save!"))

  async def socket_update(self, folder: str, savename: str) -> None: 
    message = json.dumps({
      "RequestType": "rtUpdateSave", 
      "update": {
        "saveName": savename, 
        "sourceFolder": folder, 
        "selectOnly": []
      }
    }) + "\r\n"

    response = await self.send_tcp_message_with_response(message)

    if response.get("ResponseType") != self.SUCCESS:
      raise SocketError(response.get("code", "Failed to update save!"))
  
  async def socket_keyset(self) -> int:
    message = json.dumps({
      "RequestType": "rtKeySet"
    }) + "\r\n"

    response = await self.send_tcp_message_with_response(message)

    return response.get("keyset", "FAIL!")
  
  async def socket_createsave(self, folder: str, savename: str, blocks: int) -> None:
    message = json.dumps({
      "RequestType": "rtCreateSave",
      "create": {
        "saveName": savename,
        "sourceFolder": folder,
        "blocks": blocks
      }
    }) + "\r\n"

    response = await self.send_tcp_message_with_response(message)

    if response.get("ResponseType") != self.SUCCESS:
      raise SocketError(response.get("code", "Failed to create a save!"))
    
  async def socket_decryptsdkey(self, sealed_key: PfsSKKey) -> None:
    message = json.dumps({
      "RequestType": "rtDecryptSealedKey",
      "decsdkey": {
        "sealedKey": sealed_key.as_array()
      }
    }) + "\r\n"

    response = await self.send_tcp_message_with_response(message)

    if response.get("ResponseType") == "srInvalid":
      raise SocketError("Failed to decrypt sealed key!")
    
    sealed_key.dec_key.extend(json.loads(response["json"]))