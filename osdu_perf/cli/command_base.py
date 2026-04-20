import argparse
from abc import ABC, abstractmethod


class Command(ABC):
    """Abstract base class for all CLI commands.

    Subclasses declare three class attributes and implement three methods:

    Class attributes:
        name:         Subcommand name shown in ``--help`` (e.g. ``"local"``).
        help:         One-line description shown in ``--help``.
        parent_chain: Tuple of parent subcommand names.  ``()`` for top-level
                      commands, ``("run",)`` for ``run local`` / ``run azure_load_test``.

    Methods to implement:
        register_args(parser)  – add command-specific arguments.
        validate_args(args)    – return True/False.
        execute(args)          – run the command, return exit code.
    """

    # Overridden by every concrete subclass
    name: str = ""
    help: str = ""
    parent_chain: tuple[str, ...] = ()

    # Auto-registration ---------------------------------------------------
    _registry: list[type["Command"]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only register concrete classes that declare a name
        if cls.name:
            Command._registry.append(cls)

    # Instance plumbing ----------------------------------------------------
    def __init__(self, logger):
        self.logger = logger

    @abstractmethod
    def register_args(self, parser: argparse.ArgumentParser) -> None:
        """Add arguments specific to this command."""

    @abstractmethod
    def execute(self, args) -> int:
        """Execute the command and return exit code."""

    @abstractmethod
    def validate_args(self, args) -> bool:
        """Validate command arguments."""

    def handle_error(self, error: Exception) -> int:
        """Common error handling for all commands."""
        self.logger.error(f"❌ Error: {error}")
        return 1