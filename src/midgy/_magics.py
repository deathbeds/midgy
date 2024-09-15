import builtins
from dataclasses import dataclass, field
from doctest import ELLIPSIS
from functools import lru_cache
from io import StringIO
from pathlib import Path
from shlex import split
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic
from jinja2 import Environment

from midgy.language.python import Python
from midgy.types import HTML, Css, Script, Markdown

from ._ipython import run_ipython

from .weave import quick_doctest, weave_argv
from ._argparser import parser
from traitlets import (
    Any,
    CInt,
    CUnicode,
    Dict,
    HasTraits,
    CBool,
    Instance,
    List,
    Type,
    Unicode,
    Bool,
)


class Tangle(HasTraits):
    from .containers import Containers

    noncode_blocks = CBool().tag(config=True)
    code_blocks = List(CUnicode, ["indent"]).tag(config=True)
    language = CUnicode("python").tag(config=True)
    parser = Instance(Python, (), {}).tag(config=True)
    enabled = Bool(True)
    depth = CInt()

    def __enter__(self):
        self.depth += 1

    def __exit__(self, *e):
        self.depth -= 1

    def render_lines(self, lines):
        if self.depth:
            return lines
        return self.parser.render_lines(lines)

    def eval(self, code):
        return run_ipython(self.parser.render(code))


class Weave(HasTraits):
    enabled = Bool(True)
    display = Any(None)
    unittest = CBool(False)
    doctest_flags = Any(ELLIPSIS)
    display_cls = Type("IPython.display.Markdown")

    def post_run_cell(self, result):
        from IPython.display import display, Markdown
        from IPython import get_ipython

        shell = get_ipython()
        if self.weave.enabled:
            cell = result.info.raw_cell
            for line in StringIO(cell):
                line = line.strip()
                if line:
                    if line.startswith(("%%",)):
                        break

                    display(shell.weave.display_cls(cell))
                    if shell.weave.unittest and "doctest" not in shell.tangle.code_blocks:
                        quick_doctest(cell)

                return


def get_parser(x):
    from importlib.metadata import entry_points

    return next(iter(entry_points(group="midgy", name=x.lstrip("."))), None)


@magics_class
class TangleMagic(Magics):
    @cell_magic
    def tangle(self, line, cell=""):
        from shlex import quote

        cmd = split(line) + ["--cmd", "\n" + cell]
        with self.shell.tangle:
            try:
                return weave_argv(cmd, magic=True)
            except SystemExit:
                pass


@lru_cache(1)
def get_environment():
    from jinja2 import Environment

    return Environment()


# this extension is installed by default when midgy is imported in an ipython context
def load_ipython_extension(shell):
    """initialize the tangle and weave magics for explicit use cases."""
    if shell:
        from jinja2 import Environment

        shell.user_ns.setdefault("shell", shell)
        if not shell.has_trait("tangle"):
            shell.add_traits(tangle=Instance(Tangle, (), {}))
            shell.add_traits(fence_methods=Instance(dict, (), {}))
            shell.fence_methods = shell.tangle.parser.fence_methods
        if not shell.has_trait("weave"):
            shell.add_traits(weave=Instance(Weave, (), {}))
        if not shell.has_trait("environment"):
            shell.add_traits(environment=Instance(Environment, (), {}))
            shell.environment = get_environment()
            shell.environment.globals = shell.user_global_ns
            shell.environment.globals.update(vars(builtins))
        if not shell.has_trait("_markdown_env"):
            shell.add_traits(_markdown_env=Dict({}))
        for t in (HTML, Css, Script, Markdown):
            shell.user_ns[t.__name__] = t

        shell.register_magics(TangleMagic(shell))
        magic = shell.magics_manager.magics["cell"]["tangle"]
        shell.magics_manager.magics["cell"][""] = magic
