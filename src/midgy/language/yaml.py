from ..tangle import get_markdown_it
import midgy
from dataclasses import dataclass, field
from functools import partial
from io import StringIO
from re import compile
import re
import importlib
import markdown_it
import markdown_it.renderer
import pygments

__all__ = ()
YAML = "yaml"
TOML = "tomllib"

DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
BLOCK, FENCE, PYCON = "code_block", "fence", "pycon"
SP, QUOTES = chr(32), (chr(34) * 3, chr(39) * 3)


def get_lang(self, token):
    """transform the fence info to the language it represents"""
    lang = token.info.split(maxsplit=1)
    return lang and lang[0] or ""
class RendererHTML(markdown_it.renderer.RendererHTML):
    def renderToken(self, tokens, idx, options, env):
        string = super().renderToken(tokens, idx, options, env)
        if len(string) == 2 and string == "<>":
            return ""

        return string


@dataclass
class Tangle:
    _type = None
    parser: object = None
    doctest_code_blocks: bool = False
    indented_code_blocks: bool = True
    fenced_code_blocks: list | None = None
    noncode_blocks: bool = True
    env: dict = None

    # constants
    COMMENT_MARKER = ""
    CONTINUE_MARKER = ""
    MIN_INDENT: int = 4

    def __init_subclass__(cls, type=None, language=None):
        if type:
            cls._mimetype = type
        if language:
            cls._pygments_language = language

    def __post_init__(self):
        if self.parser is None:
            self.parser = get_markdown_it()
            self.initalize_parser_defaults(self.parser)

        self.comment_prefix_line = isinstance(self.COMMENT_MARKER, str)

    @staticmethod
    def cls_from_lang(lang):
        from importlib.metadata import entry_points

        try:
            return next(iter(entry_points(group="midgy", name=lang.lstrip(".")))).load()
        except StopIteration:
            return

    def code_block(self, token, env):
        if self.indented_code_blocks:
            yield from self.generate_noncode(env, token)
            block = self.generate_block_lines(env, token.map[1])
            yield from self.generate_code_block_body(block, token, env)
            self.update_env(token, env)

    @classmethod
    def from_argv(cls, first=None, *args):
        if args:
            args = (first,) + args
        else:
            if isinstance(first, str):
                from shlex import split

                args = split(first)
        from ._argparser import parser

        return cls.from_namespace(parser.parse_known_args(args)[0])

    @classmethod
    def from_namespace(cls, ns):
        ns = dict((k, v) for k, v in vars(ns).items() if v is not None)
        ns.pop("file", None)
        next = cls.cls_from_lang(ns.pop("language", None))
        return next(**ns), ns

    def generate_block_lines(self, env, stop=None):
        """iterate through the lines in a buffer"""
        if stop is None:
            yield from env["source"]
        else:
            while env["last_line"] < stop:
                x = self.readline(env)
                yield x

    def generate_code_block_body(self, block, token, env):
        yield from self.generate_dedent_block(block, env["min_indent"])

    def generate_comment(self, block, token, env, *, prepend="", **kwargs):
        if self.comment_prefix_line:
            pre = SP * self.generate_env_indent(env, token) + self.COMMENT_MARKER
            yield from self.generate_wrapped_lines(block, pre=pre, lead=prepend)
        else:
            self.generate_wrapped_lines(
                block, lead=(prepend or "") + self.COMMENT_MARKER[0], trail=self.COMMENT_MARKER[1]
            )

    def generate_dedent_block(self, block, dedent):
        yield from (x[dedent:] if len(x) > 1 else x for x in block)

    def generate_env_indent(self, env, next=None):
        return 0

    def generate_noncode(self, env, next=None):
        block = self.generate_block_lines(env, next.map[0] if next else None)
        if self.noncode_blocks:
            yield from self.generate_noncode_string(block, next, env)
        else:
            yield from self.generate_comment(block, None, env)

    def generate_noncode_string(self, block, next=None, env=None):
        yield from block

    def generate_tokens(self, tokens, env=None, src=None, stop=None, target=None):
        for token in tokens:
            if self.is_code_block(token):
                env["next_code"] = token
            for line in self.render_token(token, env):
                print(line, file=target, sep="", end="")

        # handle anything left in the buffer
        for line in self.generate_noncode(env, stop):
            print(line, file=target, sep="", end="")

    def generate_wrapped_lines(self, lines, lead="", pre="", trail="", continuation=""):
        """a utility function to manipulate a buffer of content line-by-line."""
        # can do this better with buffers
        whitespace, any, continued = StringIO(), False, False
        for line in lines:
            length = len(line.rstrip())
            if length:
                if any:
                    yield whitespace.getvalue()
                else:
                    for i, l in enumerate(whitespace):
                        yield from (continuation, l[-1])
                if self.CONTINUE_MARKER:
                    continued = line[length - 1] == self.CONTINUE_MARKER
                    if continued:
                        length -= 2  # cause of the escape?
                yield pre
                yield lead
                yield line[:length]
                lead, any, whitespace = "", True, StringIO(line[length:])
            else:
                whitespace.write(line)
        if any:
            yield trail
        if any:
            whitespace.seek(0)
            if continued:
                for i, line in enumerate(whitespace):
                    yield pre * bool(i)
                    yield line[0 if i else 2 : -1]
                    yield self.CONTINUE_MARKER
                    yield line[-1]
            else:
                for i, line in enumerate(whitespace):
                    yield pre * bool(i) + line
        else:
            yield from map((continuation or "").__add__, whitespace)

    def initialize_env(self, src, tokens):
        """initialize the parser environment indents"""
        env = dict(**self.env or dict(), source=StringIO(src), last_line=0, last_indent=0)
        for token in filter(self.is_code_block, tokens):  # iterate through the tokens
            if not token.meta.get("is_magic"):
                env["min_indent"] = min(env.get("min_indent", 9999), token.meta.get("min_indent", 0))
        env.setdefault("min_indent", 0)
        env.setdefault("whitespace", StringIO())
        return env

    def initialize_parser(self):
        return self.initalize_parser_defaults(self.parser)

    def initalize_parser_defaults(self, parser):
        # our tangling system adds extra conventions to commonmark:
        ## extend indented code to recognize doctest syntax in-line
        ## replace the indented code lexer to recognize doctests and append metadata.
        ## recognize shebang lines at the beginning of a document.
        ## recognize front-matter at the beginning of document of following shebangs
        from mdit_py_plugins import deflist, footnote
        from midgy.front_matter import _front_matter_lexer, _shebang_lexer
        from midgy.lexers import code_fence_lexer, doctest_lexer, code_lexer

        parser.block.ruler.before("code", "doctest", doctest_lexer)
        parser.block.ruler.disable("code")
        # our indented code captures doctests in indented blocks
        parser.block.ruler.after("doctest", "code", code_lexer)
        parser.disable(FENCE)
        # our code fence captures indent information
        parser.block.ruler.after("code", FENCE, code_fence_lexer)
        # shebang because this markdown is code
        parser.block.ruler.before("table", "shebang", _shebang_lexer)
        parser.block.ruler.before("table", "front_matter", _front_matter_lexer)
        parser.use(footnote.footnote_plugin).use(deflist.deflist_plugin)
        parser.disable("footnote_tail")
        parser.code_formatter = pygments.formatters.get_formatter_by_name("html")
        parser.options["highlight"] = self.highlight
        return parser

    def highlight(self, source, lang, attrs):
        try:
            return pygments.highlight(
                source,
                pygments.lexers.get_lexer_by_name(lang),
                self.parser.code_formatter,
            )
        except:
            return f"""<pre><code class="{lang}">{source}</code></pre>"""

    def is_code_block(self, token):
        """is the token a code block entry"""
        if self.indented_code_blocks and token.type == BLOCK:
            return self.indented_code_blocks
        elif token.type == FENCE:
            tokens = (token.info or "%").split(maxsplit=1) or [""]
            return tokens[0] in (self.fenced_code_blocks or ())
        return False

    def parse(self, src, env=None):
        return self.parser.parse(src, env)

    def readline(self, env):
        try:
            return env["source"].readline()
        finally:
            env["last_line"] += 1

    def render(self, src):
        return self.render_tokens(self.parse(src), src=src)

    def render_token(self, token, env):
        if token:
            method = getattr(self, token.type, None)
            if method:
                yield from method(token, env) or ()

    def render_tokens(self, tokens, env=None, src=None, stop=None, target=None):
        """render parsed markdown tokens"""
        if target is None:
            target = StringIO()

        if env is None:
            env = self.initialize_env(src, tokens)

        self.generate_tokens(tokens, env=env, src=src, stop=stop, target=target)

        return target.getvalue()  # return the value of the target, a format string.

    def shebang(self, token, env):
        yield from self.generate_block_lines(env, token.map[1])

    def update_env(self, token, env, **kwargs):
        """update the state of the environment"""
I = lambda *x: x and x[0] or None
def get_ep(value):
    return importlib.metadata.EntryPoint(None, value, None).load()
@dataclass
class Yaml(Tangle):
    noncode_blocks = True
    COMMENT_MARKER = "# "
    update_env = midgy.language.python.Python.update_env
    get_indent = midgy.language.python.Python.get_indent
    noncode_string = midgy.language.python.Python.noncode_string
    escape = staticmethod(midgy.language.python.Python.escape)
    noncode_whitespace = midgy.language.python.Python.noncode_whitespace

    fenced_code_blocks: list = field(default_factory=["yaml", "yml"].copy)
    fence_methods: dict = field(default_factory=dict(
        json="json:loads",
        json5="json5:loads",
        yaml=I,
        yml=I,
        toml=f"{TOML}:loads"
    ).copy)
    
    def update_env(self, token, env):
        env["indented"] = token.content.rstrip().endswith(("|", ">"))
        env["indented_block"] = token.content.rstrip().endswith((":",))

    def noncode_block(self, env, next=None, comment=False, **kwargs):
        """dispatch comments of bock strings for noncode blocks"""
        from markdown_it.token import Token

        if isinstance(next, Token):
            next = next.map[0]
        block = self.generate_block_lines(env, next)
        if comment or env.get("comment") or not self.noncode_blocks:
            yield from self.generate_comment(block, None, env, **kwargs)
        else:
            yield from self.noncode_string(block, next, env, **kwargs)
    
    def generate_noncode(self, env, token):
        block = super().generate_noncode(env, token)
        if env.get("indented"):
            yield from map((" " * self.get_indent(env)).__add__, block)
        else:
            yield from self.generate_comment(block, token, env, prepend="")
            
    def fence(self, token, env):
        """dispatch different renderings of code fences."""
        if "~" not in token.markup:
            # tilde fences do not tangle. maybe make this configurable
            lang = self.get_lang(token)
            # format the prior non-code
            yield from self.noncode_block(env, token)
            if lang in self.fenced_code_blocks:
                # render fence as python code
                yield from self.fence_code(token, env)
            else:
                # render fence as block string
                yield from self.fence_noncode(token, env)
    
    def fence_code(self, token, env):
        """render code fence as python code"""

        # comment out the first line of the fence dashes
        yield self.COMMENT_MARKER
        yield from self.generate_block_lines(env, token.map[0] + 1)

        block = self.generate_block_lines(env, token.map[1] - 1)
        if self.include_magic and token.meta.get("is_magic"):
            # render the fence content as a cell magic invocation
            yield from self.cell_magic(token, block, env)
        else:
            # dedent the code like we would an indent code block
            yield from self.generate_dedent_block(block, env["min_indent"])

        # comment out the last of fence dashes
        yield self.COMMENT_MARKER
        yield from self.generate_block_lines(env, token.map[1])
        self.update_env(token, env, quoted=False, continued=False)
        # we don't allow for continued blocks or explicit quotes with code fences.
        # these affordances are only possible with indented code blocks.
        # continutation can be acheived using parenthesis continuation
    
    def fence_noncode(self, token, env):
        """render a fence as a block string with an optional caller method"""
        
        closed = not token.meta.get("autoclose")
        
        method = self.get_fence_method(token)

        if isinstance(method, str):
            method = get_ep(method)
        # else:
        #     return

        
        whitespace = SP * (self.get_indent(env) + 4)
        # fence method are functions applied to block string in a fence like json, toml, tomli
        

        # parenthesis are used to group strings together and allow for methods to called on the block string.
        # group and comment out the first line of the fence dashes
        yield whitespace
        yield "# "
        yield from self.generate_block_lines(env, token.map[0] + 1)
        block = self.generate_block_lines(env, token.map[1] - closed)
        block = self.generate_dedent_block(block, token.meta.get("min_indent"))

        # if there is a method then we wanna make it yaml.
        # yaml can 
        if callable(method):
            if method:
                block = __import__("yaml").safe_dump(method("".join(block))).splitlines()

        line = ""
        for line in map(self.escape, map(whitespace.__add__, block)):
            yield line

        if not line.endswith("\n"):
            yield "\n"
            
        # close the fence group and comment out the last fence dashes
        # this syntax restricuts from using line continuations like indented code blocks
        # if the comment were dropped then we could use continuations
        
        rest = iter(["\n"])
        if closed:
            yield whitespace
            yield "# "
            rest = self.generate_block_lines(env, token.map[1])
        yield from rest

    def get_fence_method(self, token):
        """map the code fence info to python method"""
        lang = self.get_lang(token)
        method = self.fence_methods.get(lang, lang)
        if ":" in method:
            return method
        return ""

    def get_lang(self, token):
        """transform the fence info to the language it represents"""
        lang = token.info.split(maxsplit=1)
        return lang and lang[0] or ""
    
def load_ipython_extension(shell):
    shell.register_magic_function(yaml_magic, "cell", "yaml")

parser = __import__("argparse").ArgumentParser()

parser.add_argument("name", default=None, nargs="?") 

def yaml_magic(line, cell):
    from IPython.display import HTML, display   
    args, rest = parser.parse_known_args(__import__
                                         ("shlex").split(line))    
    import midgy.language.yaml, yaml
    shell = get_ipython()
    input = midgy.language.yaml.Yaml().render(cell)
    if args.name:
        shell.user_ns[args.name]
    display(HTML(shell.markdown.render(cell)))
    return yaml.safe_load(input)
    

    