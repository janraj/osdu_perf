import argparse
from .command_base import Command
from . import commands  # noqa: F401  — triggers __init_subclass__ registration


class CommandRegistry:
    """Discovers Command subclasses, builds the argparse tree, and resolves
    the target command from parsed args — replacing both ArgParser and
    CommandFactory."""

    def __init__(self, logger):
        self.logger = logger

    def build_parser(self) -> argparse.ArgumentParser:
        """Walk every registered Command subclass and build the full
        argparse hierarchy from their ``parent_chain`` and ``name``."""
        root = argparse.ArgumentParser(
            description="OSDU Performance Testing Framework CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  osdu_perf init storage              # Initialize tests for storage service
  osdu_perf init search --force       # Force overwrite existing files
  osdu_perf version                   # Show version information
  osdu_perf run local --scenario record_size_1KB
""",
        )
        root_subparsers = root.add_subparsers(
            dest="command", help="Available commands", required=True
        )

        # Cache for intermediate subparser groups keyed by parent path
        # e.g. "run" -> the subparsers action attached to the "run" parser
        subparsers_cache: dict[str, argparse._SubParsersAction] = {
            "": root_subparsers,
        }

        for cmd_cls in sorted(Command._registry, key=lambda c: c.name):
            parent_key = "/".join(cmd_cls.parent_chain)

            # Ensure every intermediate parent parser exists
            self._ensure_parents(root_subparsers, subparsers_cache, cmd_cls.parent_chain)

            parent_subparsers = subparsers_cache[parent_key]
            sub = parent_subparsers.add_parser(cmd_cls.name, help=cmd_cls.help)

            # Let the command define its own arguments
            instance = cmd_cls(self.logger)
            instance.register_args(sub)

            # Stash the instance so resolve() can retrieve it
            sub.set_defaults(_command_instance=instance)

        return root

    @staticmethod
    def resolve(args) -> Command:
        """Return the Command instance that was set by ``set_defaults``."""
        return getattr(args, "_command_instance")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_parents(
        self,
        root_subparsers: argparse._SubParsersAction,
        cache: dict[str, argparse._SubParsersAction],
        chain: tuple[str, ...],
    ):
        """Create intermediate parsers (e.g. ``run``) if they don't exist yet."""
        for depth in range(len(chain)):
            key = "/".join(chain[: depth + 1])
            if key in cache:
                continue

            # Parent subparsers action that this intermediate lives under
            parent_key = "/".join(chain[:depth])
            parent_subparsers = cache[parent_key]

            intermediate = parent_subparsers.add_parser(
                chain[depth], help=f"{chain[depth].capitalize()} commands"
            )
            intermediate_subs = intermediate.add_subparsers(
                dest=f"{chain[depth]}_command",
                help=f"{chain[depth].capitalize()} command options",
                required=True,
            )
            cache[key] = intermediate_subs
