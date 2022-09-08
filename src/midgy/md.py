from io import StringIO
from textwrap import indent

from markdown_it import MarkdownIt

SPACE = " "


class Renderer(MarkdownIt):
    """the base renderer for translating markdown input"""

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
    """a renderer_cls to be used with a Renderer"""

    def generic_lines(self, env, next=None):
        yield from self.yieldlines(next.map[0], env) if next else env["source"]

    def generic(self, env, next=None):
        return "".join(self.generic_lines(env, next))

    def walk(self, tokens, options, env):
        for token in tokens:
            if hasattr(self, token.type):
                yield getattr(self, token.type)(token, options, env)
        else:
            yield self.generic(env)

    def render(self, tokens, options, env):
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



def main(file=None, module=None, code=None):
    """compare markdown and python sources"""
    if file is module is code is None:
        from .__main__ import default_parser
        default_parser(__name__)

def parser(parent=None):
    if parent is None:
        from .__main__ import default_parser as parent
        parent = parent(__name__, description=__doc__)
        parent.add_argument("-p", "--py", action="store_false")
    


if __name__ == "__main__":
    from .__main__ import default_parser as parent
    parser = default_parser(__name__, description=__doc__)
    run