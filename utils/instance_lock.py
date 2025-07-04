import asyncio
from dataclasses import dataclass, field
from utils.exceptions import InstanceError

MAXIMUM_INSTANCES_AT_ONCE = 32
MAXIMUM_INSTANCES_PER_USER = 1

@dataclass
class InstanceLock:
    maximum_instances: int
    maximum_instances_per_user: int

    instances: dict[int, int] = field(default_factory=dict)
    instances_len: int = 0

    def __post_init__(self) -> None:
        self.lock = asyncio.Lock()

    async def acquire(self, disc_userid: int) -> None:
        async with self.lock:
            if self.instances_len == self.maximum_instances:
                raise InstanceError(f"There are no available slots! Maximum of {self.maximum_instances} reached. Please try again later.")
            
            user_occupied_slots = self.instances.get(disc_userid, 0)
            if user_occupied_slots == self.maximum_instances_per_user:
                raise InstanceError(f"You can only have {self.maximum_instances_per_user} active instance(s) at a time!")
            
            self.instances[disc_userid] = user_occupied_slots + 1
            self.instances_len += 1
    
    async def release(self, disc_userid: int) -> None:
        async with self.lock:
            assert disc_userid in self.instances and self.instances_len > 0

            self.instances[disc_userid] -= 1
            self.instances_len -= 1

            if self.instances[disc_userid] == 0:
                del self.instances[disc_userid]

INSTANCE_LOCK_global = InstanceLock(MAXIMUM_INSTANCES_AT_ONCE, MAXIMUM_INSTANCES_PER_USER)