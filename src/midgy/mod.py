from importnb import Notebook

from .py import Python, Renderer


class Markdown(Notebook):
    """an importnb extension for pidgy documents"""

    extensions = ".py.md", ".md", ".md.ipynb"
    tangle = Renderer(renderer_cls=Python)

    def get_data(self, path):
        if self.path.endswith(".md"):
            self.source = self.decode()
            return self.code(self.source)
        return super(Notebook, self).get_data(path)

    def code(self, str):
        return super().code(self.tangle.render("".join(str)))

    get_source = get_data = get_data
