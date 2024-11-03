from dataclasses import dataclass, field
from doctest import DocTestFinder, DocTestRunner
from importlib import import_module
from shlex import split
from typing import Any
from .tangle import Tangle
from ._argparser import parser


def get_environment():
    from ._magics import get_environment
    from IPython import get_ipython

    shell = get_ipython()
    if shell.has_trait("environment"):
        return shell.environment
    return get_environment()


@dataclass
class Weave:
    source: str = None
    parser: Tangle = None
    out: str = None
    env: dict = None
    tokens: list = None
    environment: Any = field(default_factory=get_environment)


def weave(
    cmd=None,
    file=None,
    module=None,
    run=True,
    show=False,
    language=None,
    extra=None,
    debug=False,
    tokens=False,
    weave=True,
    unittest=False,
    format=False,
    magic=False,
    name=None,
    html=True,
    lists=True,
    defs=False,
    unsafe=False,
    **kwargs,
):
    from IPython import get_ipython

    shell = get_ipython()
    unittest = kwargs.pop("unittest", unittest)
    env = None
    if shell and language is None:
        parser = shell.tangle.parser
        env = shell._markdown_env
    else:
        parser = Tangle.cls_from_lang(language or "python")(**kwargs)
    if unsafe:
        cmd = shell.environment.from_string(cmd).render()
    if name is not None:
        # allow exposing the source code as a named variable
        # this is a great optional feature for debugging or reusing code.
        get_ipython().user_ns[name] = cmd
    self = Weave(source=cmd, parser=parser, env=env)
    self.tokens = self.parser.parse(self.source, self.env)
    if tokens:
        print(self.tokens)
    self.env = self.parser.initialize_env(self.source, self.tokens)
    out = self.parser.render_tokens(self.tokens, self.env, self.source)
    if format:
        out = blacken(out)
    self.out = Block(out)

    if show:
        # rich uses bbcode to format strings so we need to duck that
        print(self.out)

    try:
        if run:
            return self.parser.eval(self.out)
    finally:
        if unittest and not self.parser.doctest_code_blocks:
            quick_doctest(self.source)

        data = {"text/x-python": self.out}
        from IPython.display import display

        if weave and self.tokens[0].map[0] == int(magic):
            if html:
                output = self.parser.parser.render(
                    self.environment.from_string(self.source).render(), env
                ).rstrip()
                while output.endswith("< />"):
                    output = output.removesuffix("< />")
                data.update({"text/html": output})
                if env:
                    env.pop("duplicate_refs", None)
            else:
                data.update({"text/markdown": self.environment.from_string(self.source).render()})
        display(data, raw=True)


def blacken(string):
    import black

    return black.format_str(string, mode=black.FileMode())


def quick_doctest(source, name="__main__"):
    from doctest import run_docstring_examples, ELLIPSIS
    from IPython import get_ipython

    shell = get_ipython()
    optionflags = shell.weave.doctest_flags or ELLIPSIS
    verbose = False
    # this should returned a structured data repr
    finder = DocTestFinder(verbose=verbose, recurse=False)
    runner = DocTestRunner(verbose=verbose, optionflags=optionflags)
    compileflags = None
    globs = dict(vars(import_module(name)))
    for test in finder.find(source, name, globs=globs):
        for example in test.examples:
            example.source = "".join(shell.transform_cell(example.source))
        runner.run(test, compileflags=compileflags)


def weave_argv(argv, magic=False):
    if isinstance(argv, str):
        argv = split(argv)
    ns, extra = parser.parse_known_args(argv)
    ns = dict(vars(ns))
    ns.setdefault("magic", magic)
    return weave(**ns, extra=extra)


class Block(str):
    __repr__ = str.__str__
