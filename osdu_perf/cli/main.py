import os 
import sys
from .command_registry import CommandRegistry
from osdu_perf.utils.logger import get_logger

def main():
    """Main CLI entry point for console script."""
    # Ensure gevent is disabled to avoid conflicts
    os.environ['GEVENT_SUPPORT'] = 'False'
    os.environ['NO_GEVENT_MONKEY_PATCH'] = '1'
    logger = get_logger('CLI')
    logger.debug(f"disable gevent monkey patch: {os.environ['NO_GEVENT_MONKEY_PATCH']}")

    registry = CommandRegistry(logger)
    parser = registry.build_parser()
    args = parser.parse_args()

    # Resolve and execute — no if/else routing
    command = registry.resolve(args)
    exit_code = command.execute(args)

    if exit_code != 0:
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
