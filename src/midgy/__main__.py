from ast import arg
from pathlib import Path
from sys import stderr, stdout
from argparse import ArgumentParser

parser = ArgumentParser("midgy", description="run markdown files")
sub = parser.add_subparsers()
run = sub.add_parser("run")
run.add_argument("-m", "--module", help="python path.")
run.add_argument("-c", "--code", help="raw code.")
run.add_argument(
    "file", nargs="?", type=Path, help="input file or globs to execute."
)
run.add_argument(
    "-d",
    "--doctest-is-code",
    action="store_true",
    help="include doctest input in code generation.",
    dest="include_doctest",
)
from .run import run as run_method

run.set_defaults(func=run_method)
convert = sub.add_parser("convert")

subs = {"run", "convert"}
try:
    # set up rich
    import importnb
    from rich import print
    from rich.traceback import install

    install(suppress=[])
except ModuleNotFoundError:
    pass


def main(parser=parser):
    from sys import argv
    if argv[1] not in subs:
        argv.insert(1, "run")
    ns, _ = parser.parse_known_args(argv[1:])
    kw = vars(ns)
    kw.pop("func", run_method)(**kw)


if __name__ == "__main__":
    main()
