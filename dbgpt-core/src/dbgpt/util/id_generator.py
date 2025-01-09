from typing import Optional

from snowflake import Snowflake, SnowflakeGenerator

_GLOBAL_GENERATOR = SnowflakeGenerator(42)


def initialize_id_generator(
    instance: int, *, seq: int = 0, epoch: int = 0, timestamp: Optional[int] = None
):
    """Initialize the global ID generator.

    Args:
        instance (int): The identifier combining both data center and machine ID in
            traditional Snowflake algorithm. This single value serves to uniquely
            identify the source of the ID generation request within distributed
            environments. In standard Snowflake, this would be split into datacenter_id
            and worker_id, but here it is combined into one for simplicity.

        seq (int, optional): The initial sequence number for the generator. Default is
            0. The sequence number increments within the same millisecond to allow
            multiple IDs to be generated in quick succession. It resets when the
                timestamp advances.

        epoch (int, optional): The epoch time in milliseconds that acts as an offset
            for the generator. This value helps to reduce the length of the generated
            number by setting a custom "start time" for the timestamp component.
            Default is 0.

        timestamp (int, optional): The initial timestamp for the generator in
            milliseconds since epoch. If not provided, the generator will use the
            current system time. This can be used for testing or in scenarios where a
            fixed start time is required.
    """
    global _GLOBAL_GENERATOR
    _GLOBAL_GENERATOR = SnowflakeGenerator(
        instance, seq=seq, epoch=epoch, timestamp=timestamp
    )


def new_id() -> int:
    """Generate a new Snowflake ID.

    Returns:
        int: A new Snowflake ID.
    """
    return next(_GLOBAL_GENERATOR)


def parse(snowflake_id: int, epoch: int = 0) -> Snowflake:
    """Parse a Snowflake ID into its components.

    Example:
        .. code-block:: python

            from dbgpt.util.id_generator import parse, new_id

            snowflake_id = new_id()
            snowflake = parse(snowflake_id)
            print(snowflake.timestamp)
            print(snowflake.instance)
            print(snowflake.seq)
            print(snowflake.datetime)

    Args:
        snowflake_id (int): The Snowflake ID to parse.
        epoch (int, optional): The epoch time in milliseconds that acts as an offset
            for the generator.

    Returns:
        Snowflake: The parsed Snowflake object.
    """
    return Snowflake.parse(snowflake_id, epoch=epoch)
