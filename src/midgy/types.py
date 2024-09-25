# all of these types should have magic counterparts
from functools import cached_property, wraps
from midgy.tangle import get_markdown_it


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


class Markdown(String):
    def _repr_markdown_(self):
        return self

    def to_html(self):
        from IPython import get_ipython

        shell = get_ipython()
        if shell:
            from midgy._magics import get_environment

            return HTML(shell.tangle.parser.parser.render(self))
        return HTML(get_markdown_it().render(self))


class Mermaid(String):
    def _repr_markdown_(self):
        return f"""```mermaid\n{self}```"""


Md = Markdown


class SVG(HTML):
    def _repr_svg_(self):
        return self


class Dot(String):
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


class Hy(String):
    @cached_property
    def shell(self):
        import hy.repl

        class InteractiveHy(hy.repl.HyCompile):

            def __init__(self, *a, **kw):
                from IPython import get_ipython

                shell = get_ipython()
                # we'll need to scope this for non interactive versions
                if shell:
                    main = __import__("__main__")
                else:
                    raise TypeError("only interactive shells are supported for hy at the moment")
                super().__init__(main, vars(main))
                self.hy_compiler = hy.repl.HyASTCompiler(__import__(__name__))

            def __call__(self, src, *args, **kwargs):
                import builtins

                exec, eval = super().__call__(src, *args, **kwargs)
                builtins.exec(exec, vars(self.module), vars(self.module))
                return builtins.eval(eval, vars(self.module), vars(self.module))

            @classmethod
            def execute(cls, code):
                return cls()(code)

        return InteractiveHy

    def _eval(self):
        return self.shell.execute(self)

    @classmethod
    def eval(cls, code):
        return cls(code)._eval()
