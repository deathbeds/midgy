from pathlib import Path
from argparse import ArgumentParser
from .run import Markdown

parser = ArgumentParser("midgy", description="run markdown files")
sub = parser.add_subparsers(dest="subparser")
run = sub.add_parser("run")
run = Markdown.get_argparser(run)
run.add_argument(
    "-t",
    "--doctest-is-code",
    action="store_true",
    help="include doctest input in code generation.",
    dest="include_doctest",
)
convert = sub.add_parser("convert")

subs = {"run", "convert"}
try:
    # set up rich
    from rich import print
    from rich.traceback import install

    install(suppress=[])
except ModuleNotFoundError:
    pass


def main(parser=parser):
    from sys import argv

    argv = argv[1:]
    if argv[0] not in subs:
        argv.insert(0, "run")

    ns, _ = parser.parse_known_args(argv)
    ns = vars(ns)

    subparser = ns.pop("subparser")
    if subparser in {None, "run"}:
        from .run import Markdown

        Markdown.load_argv(argv[1:])
        return


if __name__ == "__main__":
    main()
