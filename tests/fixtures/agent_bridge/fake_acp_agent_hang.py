"""Fake ACP agent that hangs forever — used for timeout tests.

Reads stdin but never responds, simulating a stuck ACP agent process.
The test verifies that _ACPConnection cleanup works on timeout.
"""

import sys
import time


def main():
    # Read one line to simulate starting, then hang forever
    sys.stdin.readline()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
