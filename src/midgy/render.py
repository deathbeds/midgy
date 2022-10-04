"""render builds the machinery to translate markdown documents to code."""

from dataclasses import dataclass, field
from functools import partial
from io import StringIO
from re import compile
from textwrap import dedent

__all__ = ()

DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
DOCTEST_CHARS = DOCTEST_CHAR, DOCTEST_CHAR, DOCTEST_CHAR, 32
ESCAPE = {x: "\\" + x for x in "'\""}
ESCAPE_PATTERN = compile("[" + "".join(ESCAPE) + "]")
ELLIPSIS_CHARS = (ord("."),) * 3 + (32,)
escape = partial(ESCAPE_PATTERN.sub, lambda m: ESCAPE.get(m.group(0)))


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

    from markdown_it import MarkdownIt

    parser: object = field(default_factory=partial(MarkdownIt, "gfm-like"))
    cell_hr_length: int = 9
    include_code_fences: set = field(default_factory=set)
    include_indented_code: bool = True
    config_key: str = "py"

    def __post_init__(self):
        from mdit_py_plugins import deflist, footnote

        from .front_matter import _front_matter_lexer, _shebang_lexer

        # our tangling system adds extra conventions to commonmark:
        ## extend indented code to recognize doctest syntax in-line
        ## replace the indented code lexer to recognize doctests and append metadata.
        ## recognize shebang lines at the beginning of a document.
        ## recognize front-matter at the beginning of document of following shebangs
        self.parser.block.ruler.before("code", "doctest", _doctest_lexer)
        self.parser.block.ruler.disable("code")
        self.parser.block.ruler.after("doctest", "code", _code_lexer)
        self.parser.block.ruler.before("table", "shebang", _shebang_lexer)
        self.parser.block.ruler.before("table", "front_matter", _front_matter_lexer)
        self.parser.use(footnote.footnote_plugin).use(deflist.deflist_plugin)

    def code_block(self, token, env):
        if self.include_indented_code:
            yield from self.get_block(env, token.map[1])

    code_fence_block = code_block

    @classmethod
    def code_from_string(cls, body, **kwargs):
        """render a string"""
        return cls(**kwargs).render(body)

    def fence(self, token, env):
        if token.info in self.include_code_fences:
            return self.code_fence_block(token, env)
        method = getattr(self, f"fence_{token.info}", None)
        if method:
            return method(token, env)

    def format(self, body):
        """a function that consumers can use to format their code"""
        return body

    def get_block(self, env, stop=None):
        """iterate through the lines in a buffer"""
        if stop is None:
            yield from env["source"]
        else:
            while env["last_line"] < stop:
                yield self.readline(env)

    def non_code(self, env, next=None):
        yield from self.get_block(env, next.map[0] if next else None)

    def parse(self, src):
        return self.parser.parse(src)

    def parse_cells(self, body, *, include_cell_hr=True):
        yield from (
            x[0] for x in self.walk_cells(self.parse(body), include_cell_hr=include_cell_hr)
        )

    def print(self, iter, io):
        return print(*iter, file=io, sep="", end="")

    def readline(self, env):
        try:
            return env["source"].readline()
        finally:
            env["last_line"] += 1

    def render(self, src, format=False):
        tokens = self.parse(src)
        out = self.render_tokens(tokens, src=src)
        return self.format(out) if format else out

    def render_cells(self, src, *, include_cell_hr=True):
        tokens = self.parse(src)
        self = self.renderer_from_tokens(tokens)
        prior = self._init_env(src, tokens)
        prior_token = None
        source = prior.pop("source")
        for block, next_token in self.walk_cells(
            tokens, env=prior, include_cell_hr=include_cell_hr
        ):
            env = self._init_env(src, block)
            env["source"], env["last_line"] = source, prior["last_line"]
            prior_token and block.insert(0, prior_token)
            yield self.render_tokens(block, env=env, stop=next_token)
            prior, prior_token = env, next_token

    def render_lines(self, src):
        return dedent(self.render("".join(src))).splitlines(True)

    def renderer_from_tokens(self, tokens):
        front_matter = self._get_front_matter(tokens)
        if front_matter:
            config = front_matter.get(self.config_key, None)
            if config:
                return type(self)(**config)
        return self

    def render_tokens(self, tokens, env=None, src=None, stop=None):
        """render parsed markdown tokens"""
        target = StringIO()
        self = self.renderer_from_tokens(tokens)
        if env is None:
            env = self._init_env(src, tokens)

        for generic, code in self._walk_code_blocks(tokens):
            # we walk pairs of tokens preceding code and the code token
            # the next code token is needed as a reference for indenting
            # non-code blocks that precede the code.
            env["next_code"] = code
            for token in generic:
                # walk the non-code tokens for any markers the class defines
                # renderers for. the renderer is responsible for taking of the
                # preceding non-code blocks, this feature is needed for any logical
                # rendering conditions.
                f = getattr(self, token.type, None)
                f and self.print(f(token, env) or "", target)
            if code:
                # format and print the preceding non-code block
                self.print(self.non_code(env, code), target)

                # update the rendering environment
                env.update(
                    last_indent=code.meta["last_indent"],
                )

                # format and print
                self.print(self.code_block(code, env), target)

        # handle anything left in the buffer
        self.print(self.non_code(env, stop), target)

        return target.getvalue()  # return the value of the target, a format string.

    def wrap_lines(self, lines, lead="", pre="", trail="", continuation=""):
        """a utility function to manipulate a buffer of content line-by-line."""
        ws, any, continued = "", False, False
        for line in lines:
            LL = len(line.rstrip())
            if LL:
                continued = line[LL - 1] == "\\"
                LL -= 1 * continued
                if any:
                    yield ws
                else:
                    for i, l in enumerate(StringIO(ws)):
                        yield l[:-1] + continuation + l[-1]
                yield from (lead, line[:LL])
                any, ws = True, line[LL:]
                lead = ""
            else:
                ws += line
        if any:
            yield trail
        if continued:
            for i, line in enumerate(StringIO(ws)):
                yield from (lead, line[:-1], i and "\\" or "", line[-1])
        else:
            yield ws

    def _init_env(self, src, tokens):
        env = dict(source=StringIO(src), last_line=0, min_indent=None, last_indent=0)
        include_doctest = getattr(self, "include_doctest", False)
        for token in tokens:
            doctest = False
            if token.type == "fence":
                if token.info in self.include_code_fences:
                    env["min_indent"] = 0
                    continue
                if include_doctest:
                    doctest = token.info == "pycon"
            if doctest or (token.type == "code_block"):
                if env["min_indent"] is None:
                    env["min_indent"] = token.meta["min_indent"]
                else:
                    env["min_indent"] = min(env["min_indent"], token.meta["min_indent"])

        if env["min_indent"] is None:
            env["min_indent"] = 0
        return env

    def _get_front_matter(self, tokens):
        for token in tokens:
            if token.type == "shebang":
                continue
            if token.type == "front_matter":
                from .front_matter import load

                return load(token.content)
            return

    def walk_cells(self, tokens, *, env=None, include_cell_hr=True):
        block = []
        for token in tokens:
            if token.type == "hr":
                if (len(token.markup) - token.markup.count(" ")) > self.cell_hr_length:
                    yield (list(block), token)
                    block.clear()
                    if include_cell_hr:
                        block.append(token)
                    elif env is not None:
                        list(self.get_block(env, token))
            else:
                block.append(token)
        if block:
            yield block, None

    def _walk_code_blocks(self, tokens):
        prior = []
        for token in tokens:
            if token.type == "code_block":
                yield list(prior), token
                prior.clear()
            else:
                prior.append(token)
        yield prior, None

    del MarkdownIt


@dataclass
class DedentCodeBlock(Renderer):
    def code_block(self, token, env):
        ref = env["min_indent"]
        for line in self.get_block(env, token.map[1]):
            right = line.lstrip()
            if right:
                yield line[ref:]
                last = right
            else:
                yield line


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

    if (start - state.blkIndent) < 4:
        return False

    if state.srcCharCode[start : start + 4] == DOCTEST_CHARS:
        lead, extra, output, closed = startLine, startLine + 1, startLine + 1, False
        indent, next = state.sCount[startLine], startLine + 1
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
        )

        token.meta.update(input=[lead, extra])
        token.meta.update(output=[extra, output] if extra < output else None)

        return True
    return False
