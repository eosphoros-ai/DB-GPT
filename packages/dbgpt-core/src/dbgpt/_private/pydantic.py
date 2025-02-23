from typing import get_origin

import pydantic

if pydantic.VERSION.startswith("1."):
    PYDANTIC_VERSION = 1
    raise NotImplementedError("pydantic 1.x is not supported, please upgrade to 2.x.")
else:
    PYDANTIC_VERSION = 2
    # pydantic 2.x
    # Now we upgrade to pydantic 2.x
    from pydantic import (  # noqa: F401
        BaseModel,
        ConfigDict,
        Extra,
        Field,
        NonNegativeFloat,
        NonNegativeInt,
        PositiveFloat,
        PositiveInt,
        PrivateAttr,
        ValidationError,
        WithJsonSchema,
        field_validator,
        model_serializer,
        model_validator,
        root_validator,
        validator,
    )

    EXTRA_FORBID = "forbid"


def model_to_json(model, **kwargs) -> str:
    """Convert a pydantic model to json."""
    if PYDANTIC_VERSION == 1:
        return model.json(**kwargs)
    else:
        if "ensure_ascii" in kwargs:
            del kwargs["ensure_ascii"]
        return model.model_dump_json(**kwargs)


def model_to_dict(model, **kwargs) -> dict:
    """Convert a pydantic model to dict."""
    if PYDANTIC_VERSION == 1:
        return model.dict(**kwargs)
    else:
        return model.model_dump(**kwargs)


def model_fields(model):
    """Return the fields of a pydantic model."""
    if PYDANTIC_VERSION == 1:
        return model.__fields__
    else:
        return model.model_fields


def field_is_required(field) -> bool:
    """Return if a field is required."""
    if PYDANTIC_VERSION == 1:
        return field.required
    else:
        return field.is_required()


def field_outer_type(field):
    """Return the outer type of a field."""
    if PYDANTIC_VERSION == 1:
        return field.outer_type_
    else:
        # https://github.com/pydantic/pydantic/discussions/7217
        origin = get_origin(field.annotation)
        if origin is None:
            return field.annotation
        return origin


def field_description(field):
    """Return the description of a field."""
    if PYDANTIC_VERSION == 1:
        return field.field_info.description
    else:
        return field.description


def field_default(field):
    """Return the default value of a field."""
    if PYDANTIC_VERSION == 1:
        return field.field_info.default
    else:
        return field.default
