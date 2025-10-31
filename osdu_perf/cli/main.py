import os 
import sys
import argparse

from osdu_perf.cli.arg_parser import ArgParser

from .command_invoker import CommandInvoker
from osdu_perf.utils.logger import get_logger

def main():
    """Main CLI entry point for console script."""
    # Ensure gevent is disabled to avoid conflicts
    os.environ['GEVENT_SUPPORT'] = 'False'
    os.environ['NO_GEVENT_MONKEY_PATCH'] = '1'
    logger = get_logger('CLI')
    logger.debug(f"disable gevent monkey patch: {os.environ['NO_GEVENT_MONKEY_PATCH']}")

    parser = ArgParser(logger).create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create command invoker
    invoker = CommandInvoker(logger)

    # Determine command name
    if args.command == 'run':
        # Handle run subcommands
        command_name = args.run_command  # 'local' or 'azure_load_test'
    else:
        command_name = args.command  # 'init' or 'version'
    
    # Execute command
    exit_code = invoker.execute_command(command_name, args)

    if exit_code != 0:
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
