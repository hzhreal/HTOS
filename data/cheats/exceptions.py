class QuickCheatsError(Exception):
    """Exception raised for errors relating to quickcheats."""
    def __init__(self, message: str) -> None:
        self.message = message

class QuickCodesError(Exception):
    """Exception raised for errors relating to quick codes."""
    def __init__(self, message: str) -> None:
        self.message = message

