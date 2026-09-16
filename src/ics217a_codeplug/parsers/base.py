# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from ..models import Channel, CodeplugOptions


class Parser(ABC):
    def __init__(self, options: CodeplugOptions) -> None:
        self.options = options

    @classmethod
    @abstractmethod
    def can_handle(cls, path: Path) -> bool:
        ...

    @abstractmethod
    def parse(self, source: Path | None = None) -> Iterator[Channel]:
        ...
