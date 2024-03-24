import asyncio

class SocketError(Exception):
  """Exception raised for errors relating to the socket."""
  def __init__(self, message: str) -> None:
    self.message = message

class SocketPS:
  SUCCESS = '{"ResponseType": "srOk"}\r\n'
  def __init__(self, HOST: str, PORT: int, maxConnections: int = 16) -> None:
    self.HOST = HOST
    self.PORT = PORT
    self.semaphore = asyncio.Semaphore(maxConnections) # Maximum 16 mounts at once
  
  async def send_tcp_message_with_response(self, host: str, port: int, message: str) -> str | None:
    writer = None
    try:
      async with self.semaphore:
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(message.encode("utf-8"))
        await writer.drain()
      
        response = await reader.read(1024)

        return response.decode("utf-8")
    
    except (ConnectionError, asyncio.TimeoutError) as e:
      print(f"An error occured while sending tcp message: {e}")
      raise SocketError("An unexpected error!")
    
    finally:
      if writer is not None:
        writer.close()
        await writer.wait_closed()
      
  async def testConnection(self) -> None:
    _, writer = await asyncio.open_connection(self.HOST, self.PORT)
    writer.close()
    await writer.wait_closed()

  async def socket_dump(self, random_string: str, savename: str) -> None: 
    request = f'{{"RequestType": "rtDumpSave", "dump": {{"saveName": "{savename}", "targetFolder": "{random_string}", "selectOnly": []}}}}\r\n'
    response = await self.send_tcp_message_with_response(self.HOST, self.PORT, request)
    
    if response != self.SUCCESS:
      raise SocketError("Invalid save!")

  async def socket_update(self, random_string: str, savename: str) -> None: 
    message = f'{{"RequestType": "rtUpdateSave", "update": {{"saveName": "{savename}", "sourceFolder": "{random_string}", "selectOnly": []}}}}\r\n'
    response = await self.send_tcp_message_with_response(self.HOST, self.PORT, message)

    if response != self.SUCCESS:
      raise SocketError("Invalid save!")
