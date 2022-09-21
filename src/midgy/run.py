"""run and import markdown files as python"""
from pathlib import Path
from sys import path
from importnb import Notebook

from .python import Python


__all__ = ("Markdown", "run")


class Markdown(Notebook):
    """an importnb extension for markdown documents"""

    extensions = ".py.md", ".md", ".md.ipynb"
    render_cls = Python

    def __init__(self, fullname=None, path=None, include_doctest=False, **kwargs):
        super().__init__(fullname, path, **kwargs)
        self.render = self.render_cls(include_doctest=include_doctest)

    def get_data(self, path):
        if self.path.endswith(".md"):
            self.source = self.decode()
            return self.code(self.source)
        return super(Notebook, self).get_data(path)

    def code(self, str):
        return super().code(self.render.render("".join(str)))

    get_source = get_data


def run(file=None, module=None, code=None, dir=None, **kwargs):
    if file is module is code is None:
        from sys import argv
        from .__main__ import run as parser
        ns, _ = vars(parser.parse_known_args(argv[1:]))
        module, file, code = (
            ns.pop("module", None),
            ns.pop("file", None),
            ns.pop("code", None),
        )
        ns.pop("func", None)
        kwargs.update(ns)
    if "" not in path:
        path.insert(0, dir or "")
    if file:
        return Markdown.load_file(file, **kwargs)
    if module:
        return Markdown.load_module_as_main(file, **kwargs)
    if code:
        return eval(Python.code_from_string(code))


if __name__ == "__main__":
    from . import __main__

    run()
