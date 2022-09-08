from ast import arg
from pathlib import Path
from .tools import iter_globs, show_rich



def parse(*file, module=None, code=None):
    pass

def translate(*file, module=None, code=None):
    pass

def run(file=None, module=None, code=None):
    from .mod import Markdown
    for f in map(Path, file):
        Markdown.load(f, main=True)

def default_parser(prog="midgy", **kwargs):
    parser = ArgumentParser(prog, **kwargs)
    parser.add_argument("-m", "--module", nargs="*", help="python path.")
    parser.add_argument("-c", "--code", nargs="*", help="raw code.")
    parser.add_argument("file", nargs="*", help="input file or globs to execute.")
    return parser

from argparse import ArgumentParser

parser = ArgumentParser("midgy", description="convert markdown to python code")
sub = parser.add_subparsers(dest="command")
run_parser = sub.add_parser("run")
convert = sub.add_parser("convert")

run_parser.add_argument("-m", "--module", nargs="*", help="python path.")
run_parser.add_argument("-c", "--code", nargs="*", help="raw code.")
run_parser.add_argument("file", nargs="*", help="input file or globs to execute.")
run_parser.set_defaults(func=run)


def main(parser=parser):

    from sys import argv

    ns = parser.parse_args(argv[1:])
    kw = vars(ns)
    print(kw)
    command = kw.pop("command", None)
    kw.pop("func")(**kw)

if __name__ == "__main__":
    main()

