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
        PrivateAttr,
        ValidationError,
        root_validator,
        validator,
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
        PrivateAttr,
        ValidationError,
        root_validator,
        validator,
    )


def model_to_json(model, **kwargs):
    """Convert a pydantic model to json"""
    if PYDANTIC_VERSION == 1:
        return model.json(**kwargs)
    else:
        if "ensure_ascii" in kwargs:
            del kwargs["ensure_ascii"]
        return model.model_dump_json(**kwargs)
