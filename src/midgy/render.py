"""render builds the machinery to translate markdown documents to code."""

from dataclasses import dataclass, field
from functools import partial
from io import StringIO
from re import compile

__all__ = ()

DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
DOCTEST_CHARS = DOCTEST_CHAR, DOCTEST_CHAR, DOCTEST_CHAR, 32
ESCAPE = {x: "\\" + x for x in "'\""}
ESCAPE_PATTERN = compile("[" + "".join(ESCAPE) + "]")
ELLIPSIS_CHARS = (ord("."),) * 3 + (32,)
escape = partial(ESCAPE_PATTERN.sub, lambda m: ESCAPE.get(m.group(0)))
SP, QUOTES = chr(32), ('"' * 3, "'" * 3)
MAGIC = compile("^\s*%{2}\S+")


# the Renderer is special markdown renderer designed to produce
# line for line transformations of markdown to the converted code.
# not all languages require this, but for python it matters.
@dataclass
class Renderer:
    """the base render system for markdown to code.

    * tokenize & render markdown as code
    * line-for-line rendering
    * use indented code as fiducial markers for translation
    * augment the commonmark spec with shebang, doctest, code, and front_matter tokens
    * a reusable base class that underlies the python translation
    """

    parser: object = None
    cell_hr_length: int = 9
    include_code_fences: set = field(default_factory=set)
    include_indented_code: bool = True
    include_doctest: bool = False
    config_key: str = "py"

    def __post_init__(self):
        self.parser = self.get_parser()

    def get_parser(self):
        from markdown_it import MarkdownIt

        parser = MarkdownIt("gfm-like", options_update=dict(inline_definitions=True, langPrefix=""))
        return self.set_parser_defaults(parser)

    def set_parser_defaults(self, parser):
        # our tangling system adds extra conventions to commonmark:
        ## extend indented code to recognize doctest syntax in-line
        ## replace the indented code lexer to recognize doctests and append metadata.
        ## recognize shebang lines at the beginning of a document.
        ## recognize front-matter at the beginning of document of following shebangs
        from mdit_py_plugins import deflist, footnote
        from .front_matter import _front_matter_lexer, _shebang_lexer

        parser.block.ruler.before("code", "doctest", _doctest_lexer)
        parser.block.ruler.disable("code")
        # our indented code captures doctests in indented blocks
        parser.block.ruler.after("doctest", "code", _code_lexer)
        parser.disable("fence")
        # our code fence captures indent information
        parser.block.ruler.after("code", "fence", code_fence)
        # shebang because this markdown is code
        parser.block.ruler.before("table", "shebang", _shebang_lexer)
        parser.block.ruler.before("table", "front_matter", _front_matter_lexer)
        parser.use(footnote.footnote_plugin).use(deflist.deflist_plugin)
        parser.disable("footnote_tail")
        return parser

    def code_block(self, token, env):
        yield from self.get_block(env, token.map[1])

    @classmethod
    def code_from_string(cls, body, **kwargs):
        """render a string"""
        return cls(**kwargs).render(body)

    def fence(self, token, env):
        """the fence renderer is pluggable.

        if token_{token.info} exists then that method is called to render the token"""
        method = getattr(self, f"fence_{token.info}", None)
        if method:
            return method(token, env)

    def get_block(self, env, stop=None):
        """iterate through the lines in a buffer"""
        if stop is None:
            yield from env["source"]
        else:
            while env["last_line"] < stop:
                yield self.readline(env)

    def get_updated_env(self, token, env):
        """update the state of the environment"""
        left = token.content.rstrip()
        continued = left.endswith("\\")
        env.update(
            colon_block=left.endswith(":"), quoted_block=left.endswith(QUOTES), continued=continued
        )

    def non_code(self, env, next=None):
        yield from self.get_block(env, next.map[0] if next else None)
        if next:
            env.update(last_indent=next.meta.get("last_indent", 0))

    def parse(self, src):
        return self.parser.parse(src)

    def parse_cells(self, body, *, include_hr=True):
        yield from (x[0] for x in self.walk_cells(self.parse(body), include_hr=include_hr))

    def print(self, iter, io):
        return print(*iter, file=io, sep="", end="")

    def readline(self, env):
        try:
            return env["source"].readline()
        finally:
            env["last_line"] += 1

    def render(self, src):
        return self.render_tokens(self.parse(src), src=src)

    def render_cells(self, src, *, include_hr=True):
        tokens = self.parse(src)
        self = self.renderer_from_tokens(tokens)
        prior = self.get_initial_env(src, tokens)
        prior_token = None
        source = prior.pop("source")

        for block, next_token in self.walk_cells(tokens, env=prior, include_hr=include_hr):
            env = self.get_initial_env(src, block)
            env["source"], env["last_line"] = source, prior["last_line"]
            prior_token and block.insert(0, prior_token)
            yield self.render_tokens(block, env=env, stop=next_token)
            prior, prior_token = env, next_token

    def render_lines(self, src):
        return self.render("".join(src)).splitlines(True)

    def renderer_from_tokens(self, tokens):
        front_matter = self.get_front_matter(tokens)
        if front_matter:
            # front matter can reconfigure the parser and make a new one
            config = front_matter.get(self.config_key, None)
            if config:
                return type(self)(**config)
        return self

    def render_token(self, token, env):
        if token:
            method = getattr(self, token.type, None)
            if method:
                yield from method(token, env) or ()

    def render_tokens(self, tokens, env=None, src=None, stop=None, target=None):
        """render parsed markdown tokens"""
        if target is None:
            target = StringIO()
        self = self.renderer_from_tokens(tokens)
        if env is None:
            env = self.get_initial_env(src, tokens)
        for generic, code in self.walk_code_blocks(tokens):
            # we walk pairs of tokens preceding code and the code token
            # the next code token is needed as a reference for indenting
            # non-code blocks that precede the code.
            env["next_code"] = code
            for token in generic + [code]:
                self.print(self.render_token(token, env), target)
        # handle anything left in the buffer
        self.print(self.non_code(env, stop), target)
        return target.getvalue()  # return the value of the target, a format string.

    def get_initial_env(self, src, tokens):
        """initialize the parser environment

        peek into the tokens looking for the first code token identified."""
        env = dict(source=StringIO(src), last_line=0, last_indent=0)
        for token in tokens:  # iterate through the tokens
            if self.is_code_block(token):
                env["min_indent"] = min(
                    env.setdefault("min_indent", 9999), token.meta["min_indent"]
                )
        env.setdefault("min_indent", 0)
        return env

    def get_front_matter(self, tokens):
        for token in tokens:
            if token.type == "shebang":
                continue
            if token.type == "front_matter":
                from .front_matter import load

                return load(token.content)
            return

    def walk_cells(self, tokens, *, env=None, include_hr=True):
        """walk cells separated by mega-hrs"""
        block = []
        for token in tokens:
            if token.type == "hr":
                if (len(token.markup) - token.markup.count(" ")) > self.cell_hr_length:
                    yield (list(block), token)
                    block.clear()
                    if include_hr:
                        block.append(token)
                    elif env is not None:
                        list(self.get_block(env, token))
            else:
                block.append(token)
        if block:
            yield block, None

    def is_code_fence(self, token):
        return token.type == "fence" and token.type in self.include_code_fences

    def is_code_block(self, token):
        """is the token a code block entry"""
        if self.include_indented_code and token.type == "code_block":
            return True
        elif token.type == "fence":
            if token.info in self.include_code_fences:
                return True
            if self.include_doctest and token.info == "pycon":
                return True
        return False

    def walk_code_blocks(self, tokens):
        """separate non code blocks and blocks

        a pair of non-code/code blocks are yield when indented code is discovered."""
        prior = []
        for token in tokens:
            if self.is_code_block(token):
                yield list(prior), token
                prior.clear()
            else:
                prior.append(token)
        yield prior, None


def _code_lexer(state, start, end, silent=False):
    """a code lexer that tracks indents in the token and is aware of doctests"""
    if state.sCount[start] - state.blkIndent >= 4:
        first_indent, last_indent, next, last_line = 0, 0, start, start
        while next < end:
            if state.isEmpty(next):
                next += 1
                continue
            if state.sCount[next] - state.blkIndent >= 4:
                begin = state.bMarks[next] + state.tShift[next]
                if state.srcCharCode[begin : begin + 4] == DOCTEST_CHARS:
                    break
                if not first_indent:
                    first_indent = state.sCount[next]
                last_indent, last_line = state.sCount[next], next
                next += 1
            else:
                break
        state.line = last_line + 1
        token = state.push("code_block", "code", 0)
        token.content = state.getLines(start, state.line, 4 + state.blkIndent, True)
        token.map = [start, state.line]
        min_indent = min(
            state.sCount[i]
            for i in range(start, state.line)
            if not state.isEmpty(i) and state.sCount[i]
        )
        meta = dict(
            first_indent=first_indent,
            last_indent=last_indent,
            min_indent=min_indent,
            magic=bool(MAGIC.match(token.content)),
        )
        token.meta.update(meta)
        return True
    return False


def _doctest_lexer(state, startLine, end, silent=False):
    """a markdown-it-py plugin for doctests

    doctest are a literate programming convention in python that we
    include in the pidgy grammar. this avoids a mixing python and doctest
    code together.

    the doctest blocks:
    * extend the indented code blocks
    * do not conflict with blockquotes
    * are implicit code fences with the `pycon` info
    * can be replaced with explicit code blocks.
    """
    start = state.bMarks[startLine] + state.tShift[startLine]

    if (state.sCount[startLine] - state.blkIndent) < 4:
        return False

    if state.srcCharCode[start : start + 4] == DOCTEST_CHARS:
        lead, extra, output, closed = startLine, startLine + 1, startLine + 1, False
        indent, next, magic = state.sCount[startLine], startLine + 1, None
        while next < end:
            if state.isEmpty(next):
                break
            if state.sCount[next] < indent:
                break
            begin = state.bMarks[next] + state.tShift[next]
            if state.srcCharCode[begin : begin + 4] == DOCTEST_CHARS:
                break

            next += 1
            if (not closed) and state.srcCharCode[begin : begin + 4] == ELLIPSIS_CHARS:
                extra = next
            else:
                closed = True
                output = next
        state.line = next
        token = state.push("fence", "code", 0)
        token.info = "pycon"
        token.content = state.getLines(startLine, next, 0, True)
        token.map = [startLine, state.line]
        token.meta.update(
            first_indent=indent,
            last_indent=indent,
            min_indent=indent,
            magic=bool(MAGIC.match(token.content.lstrip().lstrip(">").lstrip())),
        )
        token.meta.update(input=[lead, extra])
        token.meta.update(output=[extra, output] if extra < output else None)

        return True
    return False


def code_fence(state, *args, **kwargs):
    from markdown_it.rules_block.fence import fence

    result = fence(state, *args, **kwargs)
    if result:
        token = state.tokens[-1]
        first_indent, last_indent = None, 0
        extent = range(token.map[0] + 1, token.map[1] - 1)
        for next in extent:
            if first_indent is None:
                first_indent = state.sCount[next]
            last_indent = state.sCount[next]
        min_indent = min([state.sCount[i] for i in extent if not state.isEmpty(i)] or [0])

        token.meta.update(
            first_indent=first_indent or 0,
            last_indent=last_indent,
            min_indent=min_indent,
            magic=bool(MAGIC.match(token.content)),
        )
    return result
