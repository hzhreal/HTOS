"""
Tool to use HTOS' second layer module, intended for debugging purposes.
"""

import sys
import os
import asyncio
import shutil
from enum import Enum
from sys import argv
from os.path import isfile

rootdir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(rootdir)
from data.crypto.helpers import extra_decrypt, extra_import
from utils.orbis import check_titleid

class Option(Enum):
    DECRYPT = "Decrypted"
    ENCRYPT = "Encrypted"

def main() -> None:
    title_id = argv[1].upper()
    opt = argv[2].lower()
    filepath = argv[3]
    if len(argv) - 1 >= 4:
        savepairname = argv[4]
    else:
        savepairname = ""

    if not check_titleid(title_id):
        print(f"Invalid title ID: {title_id}.")
        sys.exit()
    if opt == "-d":
        opt = Option.DECRYPT
    elif opt == "-e":
        opt = Option.ENCRYPT
    else:
        print(f"Invalid option: {opt}.")
        print_usage()
        sys.exit()
    if not isfile(filepath):
        print(f"{filepath} is not a file.")
        sys.exit()

    # write backup
    shutil.copyfile(filepath, filepath + ".bak")

    match opt:
        case Option.DECRYPT:
            asyncio.run(extra_decrypt(None, title_id, filepath, savepairname, True))
        case Option.ENCRYPT:
            asyncio.run(extra_import(title_id, filepath, savepairname))
    print(f"{opt.value} {filepath}.")

def print_usage() -> None:
    print(f"USAGE: python {argv[0]} <title ID> [option] <filepath> <savepairname (optional)>")
    print("OPTIONS\tExplanation")
    print("-d\tDecrypt file")
    print("-e\tEncrypt file")

if __name__ == "__main__":
    argc = len(argv)
    if (argc - 1) < 3:
        print_usage()
        sys.exit()
    main()
