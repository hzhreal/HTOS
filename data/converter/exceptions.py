class ConverterError(Exception):
    """Exception raised for errors relating to the converter."""
    def __init__(self, message: str) -> None:
        self.message = message