import pydantic

if pydantic.VERSION.startswith("1."):
    PYDANTIC_VERSION = 1
    from pydantic import (
        BaseModel,
        Extra,
        Field,
        NonNegativeFloat,
        NonNegativeInt,
        PositiveFloat,
        PositiveInt,
        ValidationError,
        root_validator,
        validator,
        PrivateAttr,
    )
else:
    PYDANTIC_VERSION = 2
    # pydantic 2.x
    from pydantic.v1 import (
        BaseModel,
        Extra,
        Field,
        NonNegativeFloat,
        NonNegativeInt,
        PositiveFloat,
        PositiveInt,
        ValidationError,
        root_validator,
        validator,
        PrivateAttr,
    )
