from ast import arg
from pathlib import Path
from sys import stderr, stdout

try:
    # set up rich
    import importnb
    from rich import print

    import midgy

    suppress = [midgy]
    from rich.traceback import install

    install(suppress=[midgy, importnb])
except ModuleNotFoundError:
    pass

def tangle_string(s, **kwargs):
    from .py import md_to_python

    return md_to_python(s, **kwargs)


def tangle_file(path, **kwargs):
    return tangle_string(path.read_text(), **kwargs)


def iter_globs(*glob, recursive=False):
    from glob import glob as find

    for g in glob:
        yield from map(Path, find(g))


def format_black(body):
    from black import FileMode, format_str

    return format_str(body, mode=FileMode())


def show_rich(source, md=False, py=True, format=False, **kwargs):
    from rich import print
    from rich.columns import Columns
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.syntax import Syntax

    py = tangle_string(source)
    lineno = True

    if format:
        py = format_black(py)

    columns = []

    if md and py:
        columns.append(Panel(Syntax(source, "gfm", line_numbers=lineno), title="md"))
        lineno = not lineno
    elif md:
        columns.append(Markdown(source))

    if py:
        if format:
            lineno = True
        columns.append(Panel(Syntax(py, "python", line_numbers=lineno), title="py"))

    print(Columns(columns, **kwargs))


def parse(*file, module=None, code=None):
    pass


def translate(*file, module=None, code=None):
    pass


def run(file=None, module=None, code=None, args=None):
    from .mod import Markdown

    for f in map(Path, file):
        Markdown.load(f, main=True)


def default_parser(prog="midgy", **kwargs):
    parser = ArgumentParser(prog, **kwargs)
    parser.add_argument("-m", "--module", nargs="*", help="python path.")
    parser.add_argument("-c", "--code", nargs="*", help="raw code.")
    parser.add_argument("file", nargs="*", help="input file or globs to execute.")
    return parser


from argparse import REMAINDER, ArgumentParser

parser = ArgumentParser("midgy", description="convert markdown to python code")
sub = parser.add_subparsers(dest="command")
run_parser = sub.add_parser("run", description="run a file or module")
convert = sub.add_parser("convert")

run_parser.add_argument("-m", "--module", nargs="*", help="python path.")
run_parser.add_argument("-c", "--code", nargs="*", help="raw code.")
run_parser.add_argument("--", dest="args", nargs=REMAINDER)
run_parser.add_argument("file", nargs="*", help="input file or globs to execute.")


def main(parser=parser):

    from sys import argv

    ns = parser.parse_args(argv[1:])
    kw = vars(ns)
    command = kw.pop("command", None)
    kw.pop("func")(**kw)


if __name__ == "__main__":
    main()
