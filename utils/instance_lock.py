import asyncio
from dataclasses import dataclass
from utils.exceptions import InstanceError

MAXIMUM_INSTANCES_AT_ONCE = 32

@dataclass
class InstanceLock:
    maximum_instances: int
    instances: int = 0

    def __post_init__(self) -> None:
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            if self.instances == self.maximum_instances:
                raise InstanceError("There are no available slots! Please try again later.")
            self.instances += 1
    
    async def release(self) -> None:
        async with self.lock:
            if self.instances > 0:
                self.instances -= 1

INSTANCE_LOCK_global = InstanceLock(MAXIMUM_INSTANCES_AT_ONCE)