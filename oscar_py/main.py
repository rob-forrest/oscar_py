#!/usr/bin/env python3
"""
OSCAR-Py Main Entry Point

Copyright (c) 2019-2025 The OSCAR Team

This file is subject to the terms and conditions of the GNU General Public
License. See the file COPYING in the main directory of the source code
for more details.

Reference: oscar/main.cpp
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QCoreApplication, QStandardPaths

# Version info
VERSION = "0.1.0-dev"
APP_NAME = "OSCAR-Py"
ORG_NAME = "OSCAR Team"
ORG_DOMAIN = "oscar-team.org"

# Configure module-level logger
logger = logging.getLogger(__name__)


def get_default_data_dir() -> Path:
    """Get the default data directory path.

    Default is ~/OSCAR Data/ following the original OSCAR convention.
    """
    documents_path = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    return Path(documents_path) / "OSCAR Data"


def setup_logging(data_dir: Path, verbose: bool = False) -> None:
    """Set up logging configuration.

    Args:
        data_dir: The data directory where log files will be stored.
        verbose: If True, set logging level to DEBUG.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create logs directory if it doesn't exist
    logs_dir = data_dir / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"oscar_py_{timestamp}.log"

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger.info(f"OSCAR-Py {VERSION} starting")
    logger.info(f"Log file: {log_file}")


def initialize_data_directory(data_dir: Path) -> bool:
    """Initialize the data directory structure.

    Creates the data directory and required subdirectories if they don't exist.

    Args:
        data_dir: The path to the data directory.

    Returns:
        True if initialization was successful, False otherwise.
    """
    try:
        # Create main data directory
        data_dir.mkdir(parents=True, exist_ok=True)

        # Create Profiles subdirectory
        profiles_dir = data_dir / "Profiles"
        profiles_dir.mkdir(exist_ok=True)

        # Verify we can write to the directory
        test_file = data_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            logger.error(f"Unable to write to data directory: {e}")
            return False

        logger.info(f"Data directory initialized: {data_dir}")
        logger.info(f"Profiles directory: {profiles_dir}")

        return True

    except (PermissionError, OSError) as e:
        logger.error(f"Failed to create data directory: {e}")
        return False


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Supported arguments:
        --profile: Name of profile to load at startup
        --datadir: Use specified folder as OSCAR data folder
        --verbose: Enable verbose logging
        --help: Show help message

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - Open Source CPAP Analysis Reporter (Python Port)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                         Start with default settings
  python main.py --profile "John Doe"    Start and load specific profile
  python main.py --datadir ~/MyData      Use custom data directory
  python main.py --verbose               Enable debug logging
        """
    )

    parser.add_argument(
        "--profile",
        type=str,
        metavar="NAME",
        help="Name of profile to load at startup. If name does not exist, "
             "shows profile selector."
    )

    parser.add_argument(
        "--datadir",
        type=str,
        metavar="FOLDER",
        help="Use FOLDER as OSCAR data folder. Relative paths are resolved "
             "from the Documents folder."
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging"
    )

    return parser.parse_args()


def resolve_data_dir(datadir_arg: str | None) -> Path:
    """Resolve the data directory path from command-line argument.

    Args:
        datadir_arg: The --datadir argument value, or None if not specified.

    Returns:
        Resolved Path to the data directory.
    """
    if datadir_arg is None:
        return get_default_data_dir()

    data_path = Path(datadir_arg)

    # If it's an absolute path, use it directly
    if data_path.is_absolute():
        return data_path

    # Otherwise, resolve relative to Documents folder
    documents_path = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    return Path(documents_path) / datadir_arg


def main() -> int:
    """Main entry point for OSCAR-Py.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Set up application metadata before creating QApplication
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setOrganizationDomain(ORG_DOMAIN)
    QCoreApplication.setApplicationVersion(VERSION)

    # Create QApplication instance
    app = QApplication(sys.argv)

    # Parse command-line arguments
    args = parse_arguments()

    # Resolve data directory
    data_dir = resolve_data_dir(args.datadir)

    # Initialize data directory
    if not initialize_data_directory(data_dir):
        QMessageBox.critical(
            None,
            "Error",
            f"Unable to create or access data directory:\n{data_dir}\n\n"
            "Please check permissions and try again."
        )
        return 1

    # Set up logging
    setup_logging(data_dir, verbose=args.verbose)

    logger.info(f"Application: {APP_NAME} {VERSION}")
    logger.info(f"Data directory: {data_dir}")
    if args.profile:
        logger.info(f"Requested profile: {args.profile}")

    # Import MainWindow here to avoid circular imports and ensure
    # QApplication exists first
    from gui.main_window import MainWindow

    # Create and show main window
    main_window = MainWindow(data_dir=data_dir)
    main_window.show()

    # If a profile was specified, attempt to open it
    if args.profile:
        # Profile loading will be handled by MainWindow
        main_window.request_profile(args.profile)

    # Run the application event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
