# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from ..models import Channel, CodeplugOptions


class Writer(ABC):
    format_name: str = ""

    def __init__(self, options: CodeplugOptions) -> None:
        self.options = options

    @abstractmethod
    def write(self, channels: Iterable[Channel], dest: Path | None) -> str:
        """Write channels. If dest is None return the output as a string."""
        ...
