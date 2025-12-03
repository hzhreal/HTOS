class FTPError(Exception):
    """Exception raised for errors relating to FTP."""
    def __init__(self, message: str) -> None:
        self.message = message

class SocketError(Exception):
    """Exception raised for errors relating to the socket."""
    def __init__(self, message: str) -> None:
        self.message = message

