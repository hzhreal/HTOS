import asyncio
import time
from dataclasses import dataclass, field
from utils.conversions import hours_to_seconds
from utils.exceptions import InstanceError

INSTANCE_TIMEOUT = hours_to_seconds(1) # a single instance will be lazily freed up every hour for each user if possible
MAXIMUM_INSTANCES_AT_ONCE = 32
MAXIMUM_INSTANCES_PER_USER = 1

@dataclass
class Instance:
    active_instances: int = 0
    timestamp: float = field(default_factory=time.time)

@dataclass
class InstanceLock:
    maximum_instances: int
    maximum_instances_per_user: int

    instances: dict[int, Instance] = field(default_factory=dict)
    instances_len: int = 0

    def __post_init__(self) -> None:
        self.lock = asyncio.Lock()

    def _timeout_handler(self, disc_userid: int) -> None:
        """Call inside lock."""

        if not disc_userid in self.instances:
            return

        epoch = time.time()
        instance = self.instances[disc_userid]

        # check if timeout has passed
        if epoch - instance.timestamp >= INSTANCE_TIMEOUT:
            # free a slot, no need to delete it because it will be used in acquire
            instance.active_instances -= 1
            self.instances_len -= 1
            instance.timestamp = epoch

    async def acquire(self, disc_userid: int) -> None:
        async with self.lock:
            self._timeout_handler(disc_userid)

            if self.instances_len == self.maximum_instances:
                raise InstanceError(f"There are no available slots! Maximum of {self.maximum_instances} reached. Please try again later.")

            instance = self.instances.get(disc_userid)
            if not instance:
                instance = Instance()
                self.instances[disc_userid] = instance

            if instance.active_instances == self.maximum_instances_per_user:
                raise InstanceError(f"You can only have {self.maximum_instances_per_user} active instance(s) at a time!")

            # every time a new slot is given, recalculate the timestamp
            instance.timestamp = time.time()

            instance.active_instances += 1
            self.instances_len += 1

    async def release(self, disc_userid: int) -> None:
        async with self.lock:
            if not disc_userid in self.instances or self.instances_len == 0:
                return

            instance = self.instances[disc_userid]
            instance.active_instances -= 1
            self.instances_len -= 1

            if instance.active_instances == 0:
                del self.instances[disc_userid]

INSTANCE_LOCK_global = InstanceLock(MAXIMUM_INSTANCES_AT_ONCE, MAXIMUM_INSTANCES_PER_USER)
