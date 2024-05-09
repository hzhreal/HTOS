import asyncio
from utils.constants import logger

class SocketError(Exception):
  """Exception raised for errors relating to the socket."""
  def __init__(self, message: str) -> None:
    self.message = message

class SocketPS:
  """Async functions to mainly interact with cecie."""
  SUCCESS = '{"ResponseType": "srOk"}\r\n'
  def __init__(self, HOST: str, PORT: int, maxConnections: int = 16) -> None:
    self.HOST = HOST
    self.PORT = PORT
    self.semaphore = asyncio.Semaphore(maxConnections) # Maximum 16 mounts at once
  
  async def send_tcp_message_with_response(self, message: str) -> str | None:
    writer = None
    try:
      async with self.semaphore:
        reader, writer = await asyncio.open_connection(self.HOST, self.PORT)
        writer.write(message.encode("utf-8"))
        await writer.drain()
      
        response = await reader.read(1024)

        logger.info(response)
        return response.decode("utf-8")
    
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

  async def socket_dump(self, random_string: str, savename: str) -> None: 
    request = f'{{"RequestType": "rtDumpSave", "dump": {{"saveName": "{savename}", "targetFolder": "{random_string}", "selectOnly": []}}}}\r\n'
    response = await self.send_tcp_message_with_response(request)
    
    if response != self.SUCCESS:
      raise SocketError("Invalid save!")

  async def socket_update(self, random_string: str, savename: str) -> None: 
    message = f'{{"RequestType": "rtUpdateSave", "update": {{"saveName": "{savename}", "sourceFolder": "{random_string}", "selectOnly": []}}}}\r\n'
    response = await self.send_tcp_message_with_response(message)

    if response != self.SUCCESS:
      raise SocketError("Invalid save!")
    
class SDKeyUnsealer(SocketPS):
  """Interact with SDKeyUnsealer if used."""
  def __init__(self, HOST: str, PORT: int, maxConnections: int = 5) -> None:
    super().__init__(HOST, PORT, maxConnections)
    
  DEC_KEY_LEN = 32
  CHKS_LEN = 2

  async def send_tcp_message_with_response(self, data: bytearray | bytes) -> bytes | str | None:
    writer = None
    try:
      async with self.semaphore:
        reader, writer = await asyncio.open_connection(self.HOST, self.PORT)
        writer.write(data)
        await writer.drain()
      
        response = await reader.read(1024)

        logger.info(response)
        parsed_response = self.parse_response(response)

        return parsed_response
    
    except (ConnectionError, asyncio.TimeoutError) as e:
      logger.error(f"An error occured while sending tcp message (SDKeyUnsealer): {e}")
      raise SocketError("Error communicating with socket.")
    
    except (SocketError) as e:
      logger.error(f"An error occured while sending tcp message (SDKeyUnsealer, expected): {e}")
      raise SocketError(e)
    
    finally:
      if writer is not None:
        writer.close()
        await writer.wait_closed()

  async def upload_key(self, enc_key: bytearray) -> bytes | str | None:
    chks_val = self.chks(enc_key)
    enc_key.extend(chks_val)

    response = await self.send_tcp_message_with_response(enc_key)
    return response
      
  def parse_response(self, response: bytes) -> bytes | str | None:
    if len(response) == self.DEC_KEY_LEN + self.CHKS_LEN:
      # check if checksum is correct
      chks_val = self.chks(bytearray(response[:self.DEC_KEY_LEN]))
      response_chks = response[self.DEC_KEY_LEN:self.DEC_KEY_LEN + self.CHKS_LEN]

      if chks_val != response_chks:
        raise SocketError("Invalid checksum!")
      
      return response[:self.DEC_KEY_LEN]
      
    return response.decode("utf-8")

  @staticmethod
  def chks(data: bytearray) -> bytes:
    data_sum = 0
    for byte in data:
      data_sum += byte
    data_sum &= 0xFF
    data_hexstr = (hex(data_sum)[2:]).encode("utf-8")

    return data_hexstr
