"""run and import markdown files as python"""
from importlib import import_module

from importnb import Notebook

from .py import Python


__all__ = "Markdown",
class Markdown(Notebook):
    """an importnb extension for pidgy documents"""

    extensions = ".py.md", ".md", ".md.ipynb"
    tangle = Python()

    def get_data(self, path):
        if self.path.endswith(".md"):
            self.source = self.decode()
            return self.code(self.source)
        return super(Notebook, self).get_data(path)

    def code(self, str):
        return super().code(self.tangle.render("".join(str)))

    get_source = get_data


def run_file(file, main=True):
    """run a markdown file as a python module"""
    return Markdown.load(file, main=main)


def run_mod(mod, main=True):
    """run a module that may be a markdown file."""
    with Markdown():
        m = import_module(mod)
    return m


def run_code(code, main=True):
    """run markdown as python code"""
    return eval(Python.code_from_string(code))


def runmd(file=None, module=None, code=None, args=None):
    """run md files, modules, code"""
    import sys

    old = sys.argv
    if args:
        sys.argv = [__name__] + list(args)

    try:
        for f in file or ():
            run_file(f)

        for m in module or ():
            run_mod(f)

        for c in code or ():
            run_code(c)
    finally:
        sys.argv = old


if __name__ == "__main__":
    from .__main__ import main, run_parser

    run_parser.set_defaults(func=runmd)
    main(run_parser)
