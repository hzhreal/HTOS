"""
Tool to use HTOS' sfo module, intended for debugging purposes.
"""

import sys
import os
import pprint
from sys import argv
from os.path import isfile

rootdir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(rootdir)

from utils.orbis_sfo import SFOContext

def main() -> None:
    sfo_path = argv[1]
    if not isfile(sfo_path):
        print(f"{sfo_path} is not a file.")
        sys.exit(1)
    with open(sfo_path, "rb") as sfo_file:
        sfo_data = sfo_file.read()

    sfo = SFOContext()
    sfo.read(sfo_data)
    param_data = sfo.get_param_data()
    pprint.pprint(param_data)

def print_usage() -> None:
    print(f"USAGE: python {argv[0]} <sfo path>")

if __name__ == "__main__":
    argc = len(argv)
    if argc - 1 < 1:
        print_usage()
        sys.exit(1)
    main()

