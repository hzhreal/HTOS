class GDapiError(Exception):
    """Exception raised for errors related to the GDapi class."""
    def __init__(self, message: str) -> None:
        self.message = message

