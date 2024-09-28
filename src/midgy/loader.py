"""run and import markdown files as python"""
from dataclasses import dataclass, field

from types import MethodType, ModuleType
from importnb import Notebook
from importnb.loader import SourceModule

from .python import Python

__all__ = ("Markdown", "run")


class MarkdownModule(SourceModule):
    def _repr_markdown_(self):
        with open(self.__file__) as file:
            return f"\t{repr(self)}\n" + file.read()


@dataclass
class Markdown(Notebook):
    """an importnb extension for markdown documents"""

    include_doctest: bool = False
    extensions: tuple = field(
        default_factory=[
            ".md",
            ".py.md",
            ".md.ipynb",
        ].copy
    )
    module_type: ModuleType = field(default=MarkdownModule)
    render_cls = Python

    def __post_init__(self):
        self.renderer = self.render_cls(include_doctest=self.include_doctest)

    def exec_module(self, module):
        super().exec_module(module)

    def code(self, str):
        return super().code(self.renderer.render("".join(str)))


if __name__ == "__main__":
    from sys import argv

    Markdown.load_argv(argv[1:])
