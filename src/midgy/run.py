"""run and import markdown files as python"""
from dataclasses import dataclass

from importnb import Notebook

from .python import Python

__all__ = ("Markdown", "run")


@dataclass
class Markdown(Notebook):
    """an importnb extension for markdown documents"""

    include_doctest: bool = False
    extensions = ".py.md", ".md", ".md.ipynb"
    render_cls = Python

    def __post_init__(self):
        self.renderer = self.render_cls(include_doctest=self.include_doctest)

    def get_data(self, path):
        if self.path.endswith(".md"):
            self.source = self.decode()
            return self.code(self.source)
        return super(Notebook, self).get_data(path)

    def code(self, str):
        return super().code(self.renderer.render("".join(str)))

    get_source = get_data


if __name__ == "__main__":
    from sys import argv

    Markdown.load_argv(argv[1:])
