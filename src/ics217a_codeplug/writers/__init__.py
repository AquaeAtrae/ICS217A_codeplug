# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from ..models import CodeplugOptions
from .base import Writer

_REGISTRY: dict[str, type[Writer]] = {}


def register_writer(cls: type[Writer]) -> type[Writer]:
    _REGISTRY[cls.format_name] = cls
    return cls


def writer_for(fmt: str, options: CodeplugOptions) -> Writer:
    if fmt not in _REGISTRY:
        raise ValueError(
            f"Unknown output format {fmt!r}. Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[fmt](options)


# Auto-register bundled writers
from .review_writer import ReviewWriter  # noqa: E402, F401
from .chirp_writer import ChirpWriter    # noqa: E402, F401
