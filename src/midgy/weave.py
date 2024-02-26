from dataclasses import dataclass
from importlib import import_module
from shlex import split

from .tangle import Tangle
from ._argparser import parser


@dataclass
class Weave:
    source: str = None
    parser: Tangle = None
    out: str = None
    env: dict = None
    tokens: list = None


def weave(
    cmd=None,
    file=None,
    module=None,
    run=True,
    show=False,
    language="python",
    extra=None,
    debug=False,
    tokens=False,
    weave=True,
    unittest=False,
    format=False,
    magic=False,
    **kwargs,
):
    try:
        from rich import print
    except ModuleNotFoundError:
        from builtins import print
    unittest = kwargs.pop("unittest", unittest)
    parser = Tangle.cls_from_lang(language)(**kwargs)
    self = Weave(source=cmd, parser=parser)
    self.tokens = self.parser.parse(self.source, self.env)
    if tokens:
        print(self.tokens)
    self.env = self.parser.initialize_env(self.source, self.tokens)
    out = self.parser.render_tokens(self.tokens, self.env, self.source)
    if format:
        out = blacken(out)
    self.out = Block(out)

    if weave and self.tokens[0].map[0] == int(magic):
        from IPython.display import display, Markdown

        display(Markdown(self.source))

    
    if show:
        # rich uses bbcode to format strings so we need to duck that
        print(self.out.replace("[", r"\["))

    try:
        if run:
            return self.parser.eval(self.out)
    finally:
        if unittest and not self.parser.doctest_code_blocks:
            quick_doctest(self.source)


def blacken(string):
    import black

    return black.format_str(string, mode=black.FileMode())


def quick_doctest(source, name="__main__"):
    from doctest import run_docstring_examples, ELLIPSIS
    from IPython import get_ipython

    shell = get_ipython()
    # this should returned a structured data repr
    return run_docstring_examples(
        source,
        dict(vars(import_module(name))),
        False,
        f"In [{shell.execution_count-1}] tests",
        None,
        shell.weave.doctest_flags or ELLIPSIS,
    )


def weave_argv(argv, magic=False):
    if isinstance(argv, str):
        argv = split(argv)
    ns, extra = parser.parse_known_args(argv)
    ns = dict(vars(ns))
    ns.setdefault("magic", magic)
    return weave(**ns, extra=extra)


class Block(str):
    __repr__ = str.__str__
