class FileError(Exception):
    """Exception raised for errors relating to a file."""
    def __init__(self, message: str) -> None:
        self.message = message

class PSNIDError(Exception):
    """Exception raised for errors relating to any Playstation Network ID."""
    def __init__(self, message: str) -> None:
        self.message = message

class InstanceError(Exception):
    """Exception raised for errors relating to the `InstanceLock`."""
    def __init__(self, message: str) -> None:
        self.message = message