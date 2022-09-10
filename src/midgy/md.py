"""markdown-it-py conventions for lexing and rendering markdown."""
from io import StringIO

from markdown_it import MarkdownIt

SPACE = " "


class MarkdownIt(MarkdownIt):
    """an overloaded MarkdownIt class

the midgy markdown lexer includes rules for:

1. shebang line

    shebangs happen when the first line of document begins with `#!`.
    we require this rule because it is only the thing that can preclude
    front matter. a feature of this rule is that it is a comment in python
    therefore the python renderer doesn't have to to do much.

2. front matter

    most front matter rules begin on the first line, but we allow for shebangs and white space.
    the front matter block is wrapped a code that is executed. `+++` and `---` trigger `toml` and `yaml`
    front matter respectively.

3. doctest

    midgy is a literate programming design, and we add doctests because they are 
    an accepted literate programming convention in python. our doctests are triggered
    inside indented code blocks.
    
"""

    def __init__(self, *args, **kwargs):
        renderer = kwargs.pop("renderer_cls", Markdown)
        super().__init__(*args or ("gfm-like",), **kwargs)
        self.init_midgy_rules()
        self.renderer_cls, self.renderer = renderer, renderer()

    def init_midgy_rules(self):
        from .lex import (
            _code_lexer,
            _shebang_lexer,
            _front_matter_lexer,
            _doctest_lexer,
        )

        self.block.ruler.before("code", "doctest", _doctest_lexer)
        self.block.ruler.disable("code")
        self.block.ruler.after("doctest", "code", _code_lexer)
        self.block.ruler.before("table", "shebang", _shebang_lexer)
        self.block.ruler.before("table", "front_matter", _front_matter_lexer)

    def initial_env(self, src):
        return dict(source=StringIO(src), target=StringIO(), last_line=0)

    def parse(self, src, env=None):
        """parse the source and return the markdown tokens"""
        if env is None:
            env = self.initial_env(src)
        return super().parse(src, env)

    def render(self, src, env=None):
        """render the source as translated python"""
        if env is None:
            env = self.initial_env(src)
        return super().render(src, env)

    def render_lines(self, src):
        """a shim that includes the tangler in the ipython transformer"""
        return self.render("".join(src)).splitlines(True)


class Markdown:
    """a renderer_cls to be used with a MarkdownIt"""

    def generic_lines(self, env, next=None):
        """yield the lines of content in a generic block."""
        yield from self.yieldlines(next.map[0], env) if next else env["source"]

    def generic(self, env, next=None):
        """a generic visitor that returns the raw content"""
        return "".join(self.generic_lines(env, next))

    def walk(self, tokens, options, env):
        """walk the markdown tokens"""
        for token in tokens:
            if hasattr(self, token.type):
                yield getattr(self, token.type)(token, options, env)
        else:
            yield self.generic(env)

    def render(self, tokens, options, env):
        """render markdown"""
        for block in self.walk(tokens, options, env):
            print(block, file=env["target"], end="")
        else:
            print(self.generic(env), file=env["target"], end="")
        return env["target"].getvalue()

    def readline(self, env):
        try:
            return env["source"].readline()
        finally:
            env["last_line"] += 1

    def yieldlines(self, stop, env):
        """read multiple lines until you want to stop"""
        while env["last_line"] < stop:
            yield self.readline(env)
