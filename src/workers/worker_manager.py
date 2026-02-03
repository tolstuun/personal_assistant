#!/usr/bin/env python3
"""
Worker manager for controlling multiple fetcher worker instances.

This script reads the fetch_worker_count setting from the database
and manages systemd service instances accordingly.

Usage:
    pa-worker-manager start   # Start workers based on fetch_worker_count
    pa-worker-manager stop    # Stop all workers
    pa-worker-manager status  # Show status of all workers
    pa-worker-manager reload  # Adjust worker count to match setting
"""

import argparse
import asyncio
import subprocess
import sys
from typing import NoReturn

from src.core.services.settings import SettingsService


async def get_worker_count() -> int:
    """
    Get the configured worker count from database.

    Returns:
        Number of workers to run.
    """
    try:
        service = SettingsService()
        count = await service.get("fetch_worker_count")
        return int(count)
    except Exception as e:
        print(f"Warning: Could not read fetch_worker_count from database: {e}")
        print("Using default value: 3")
        return 3


def get_running_workers() -> list[int]:
    """
    Get list of currently running worker instance numbers.

    Returns:
        List of running worker instance numbers.
    """
    try:
        result = subprocess.run(
            [
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-legend",
                "pa-fetcher@*",
            ],
            capture_output=True,
            text=True,
        )
        workers = []
        for line in result.stdout.strip().split("\n"):
            if line and "pa-fetcher@" in line:
                # Extract instance number from "pa-fetcher@1.service"
                unit = line.split()[0]
                instance = unit.split("@")[1].split(".")[0]
                workers.append(int(instance))
        return sorted(workers)
    except Exception as e:
        print(f"Error getting running workers: {e}")
        return []


def start_worker(instance: int) -> bool:
    """
    Start a single worker instance.

    Args:
        instance: Worker instance number.

    Returns:
        True if started successfully.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "start", f"pa-fetcher@{instance}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  Started pa-fetcher@{instance}")
            return True
        else:
            print(f"  Failed to start pa-fetcher@{instance}: {result.stderr}")
            return False
    except Exception as e:
        print(f"  Error starting pa-fetcher@{instance}: {e}")
        return False


def stop_worker(instance: int) -> bool:
    """
    Stop a single worker instance.

    Args:
        instance: Worker instance number.

    Returns:
        True if stopped successfully.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "stop", f"pa-fetcher@{instance}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  Stopped pa-fetcher@{instance}")
            return True
        else:
            print(f"  Failed to stop pa-fetcher@{instance}: {result.stderr}")
            return False
    except Exception as e:
        print(f"  Error stopping pa-fetcher@{instance}: {e}")
        return False


def enable_worker(instance: int) -> bool:
    """
    Enable a worker instance to start on boot.

    Args:
        instance: Worker instance number.

    Returns:
        True if enabled successfully.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "enable", f"pa-fetcher@{instance}"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def disable_worker(instance: int) -> bool:
    """
    Disable a worker instance from starting on boot.

    Args:
        instance: Worker instance number.

    Returns:
        True if disabled successfully.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "disable", f"pa-fetcher@{instance}"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


async def cmd_start(enable_on_boot: bool = True) -> int:
    """
    Start workers based on fetch_worker_count setting.

    Args:
        enable_on_boot: Whether to enable workers to start on boot.

    Returns:
        Exit code.
    """
    target_count = await get_worker_count()
    running = get_running_workers()

    print(f"Target worker count: {target_count}")
    print(f"Currently running: {len(running)} workers")

    if len(running) >= target_count:
        print("Already running enough workers.")
        return 0

    # Start additional workers
    print(f"\nStarting {target_count - len(running)} additional workers...")
    started = 0
    for i in range(1, target_count + 1):
        if i not in running:
            if start_worker(i):
                started += 1
                if enable_on_boot:
                    enable_worker(i)

    print(f"\nStarted {started} workers. Total running: {len(running) + started}")
    return 0


async def cmd_stop() -> int:
    """
    Stop all running workers.

    Returns:
        Exit code.
    """
    running = get_running_workers()

    if not running:
        print("No workers are running.")
        return 0

    print(f"Stopping {len(running)} workers...")
    stopped = 0
    for instance in running:
        if stop_worker(instance):
            stopped += 1
            disable_worker(instance)

    print(f"\nStopped {stopped} workers.")
    return 0


async def cmd_status() -> int:
    """
    Show status of all workers.

    Returns:
        Exit code.
    """
    target_count = await get_worker_count()
    running = get_running_workers()

    print(f"Configured worker count: {target_count}")
    print(f"Running workers: {len(running)}")

    if running:
        print(f"\nRunning instances: {', '.join(str(i) for i in running)}")

    # Show systemctl status for running workers
    if running:
        print("\n" + "=" * 60)
        for instance in running:
            print(f"\n--- Worker {instance} ---")
            subprocess.run(
                ["systemctl", "status", f"pa-fetcher@{instance}", "--no-pager", "-n", "3"],
            )

    return 0


async def cmd_reload() -> int:
    """
    Adjust worker count to match the fetch_worker_count setting.

    Starts new workers if needed, stops excess workers if there are too many.

    Returns:
        Exit code.
    """
    target_count = await get_worker_count()
    running = get_running_workers()

    print(f"Target worker count: {target_count}")
    print(f"Currently running: {len(running)} workers")

    if len(running) == target_count:
        print("Worker count already matches target.")
        return 0

    if len(running) < target_count:
        # Start additional workers
        to_start = target_count - len(running)
        print(f"\nStarting {to_start} additional workers...")
        for i in range(1, target_count + 1):
            if i not in running:
                start_worker(i)
                enable_worker(i)
    else:
        # Stop excess workers (stop highest numbered first)
        to_stop = len(running) - target_count
        print(f"\nStopping {to_stop} excess workers...")
        for instance in sorted(running, reverse=True)[:to_stop]:
            stop_worker(instance)
            disable_worker(instance)

    return 0


def main() -> NoReturn:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage fetcher worker instances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pa-worker-manager start    Start workers based on fetch_worker_count setting
  pa-worker-manager stop     Stop all running workers
  pa-worker-manager status   Show status of all workers
  pa-worker-manager reload   Adjust worker count to match setting

The fetch_worker_count setting can be changed in the admin UI at /admin/settings
        """,
    )
    parser.add_argument(
        "command",
        choices=["start", "stop", "status", "reload"],
        help="Command to execute",
    )
    parser.add_argument(
        "--no-enable",
        action="store_true",
        help="Don't enable workers to start on boot (for 'start' command)",
    )

    args = parser.parse_args()

    # Run the appropriate command
    if args.command == "start":
        exit_code = asyncio.run(cmd_start(enable_on_boot=not args.no_enable))
    elif args.command == "stop":
        exit_code = asyncio.run(cmd_stop())
    elif args.command == "status":
        exit_code = asyncio.run(cmd_status())
    elif args.command == "reload":
        exit_code = asyncio.run(cmd_reload())
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
