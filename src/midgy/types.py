from functools import wraps


def enforce_cls(callable):
    @wraps(callable)
    def main(self, *args, **kwargs):
        return type(self)(callable(self, *args, **kwargs))

    return main


class String(str):
    @property
    def data(self):
        return self

    __add__ = enforce_cls(str.__add__)
    __mul__ = enforce_cls(str.__mul__)
    __rmul__ = enforce_cls(str.__rmul__)
    capitalize = enforce_cls(str.capitalize)
    format = enforce_cls(str.format)
    removeprefix = enforce_cls(str.removeprefix)
    removesuffix = enforce_cls(str.removesuffix)
    replace = enforce_cls(str.replace)
    strip = enforce_cls(str.strip)
    lstrip = enforce_cls(str.lstrip)
    rstrip = enforce_cls(str.rstrip)
    upper = enforce_cls(str.upper)
    lower = enforce_cls(str.lower)

    @enforce_cls
    def render(self, *args, **kwargs):
        from IPython import get_ipython

        shell = get_ipython()
        if shell:
            from midgy._magics import get_environment

            return get_environment().from_string(self).render(*args, **kwargs)
        object.__getattribute__(self, "render")


class HTML(String):
    tag = ""

    def _repr_html_(self):
        html = ""
        if self.tag:
            html += f"<{self.tag}>"
        html += self
        if self.tag:
            html += f"</{self.tag}>"
        return html


class Css(HTML):
    tag = "style"


class Script(HTML):
    tag = "script"


class Markdown(str):
    def _repr_markdown_(self):
        return self


class SVG(HTML):
    def _repr_svg_(self):
        return self


class DOT(String):
    def graphviz(
        self,
    ):
        from graphviz import Source

        return Source(self)

    def _repr_svg_(self):
        try:
            return self.graphviz()._repr_image_svg_xml()
        except (ModuleNotFoundError, ImportError):
            pass
