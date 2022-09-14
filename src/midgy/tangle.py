"""tangle builds the machinery to translate markdown documents to code."""

from dataclasses import dataclass, field
from functools import partial
from io import StringIO
from re import compile

__all__ = "Tangle", "escape"

DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
DOCTEST_CHARS = DOCTEST_CHAR, DOCTEST_CHAR, DOCTEST_CHAR
ESCAPE = {x: "\\" + x for x in "'\""}
ESCAPE_PATTERN = compile("[" + "".join(ESCAPE) + "]")

escape = partial(ESCAPE_PATTERN.sub, lambda m: ESCAPE.get(m.group(0)))


# the Tangle is special markdown renderer designed to produce
# line for line transformations of markdown to the converted code.
# not all languages require this, but for python it matters.
@dataclass
class Tangle:
    """tangle markdown to code.

    * tokenize & render markdown as code
    * line-for-line rendering
    * use indented code as fiducial markers for translation
    * augment the commonmark spec with shebang, doctest, code, and front_matter tokens
    * a reusable base class that underlies the python translation
    """

    from markdown_it import MarkdownIt

    parser: object = field(default_factory=MarkdownIt)
    cell_hr_length: int = 9

    def __post_init__(self):
        from .front_matter import (
            _front_matter_lexer,
            _shebang_lexer,
        )

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

    def code_block(self, token, env):
        yield from self.get_block(env, token.map[1])

    @classmethod
    def code_from_string(cls, body, **kwargs):
        """tangle a string"""
        return cls(**kwargs).render(body)

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

    def parse_cells(self, body):
        return self._walk_cells(self.parse(body))

    def print(self, iter, io):
        return print(*iter, file=io, sep="", end="")

    def readline(self, env):
        try:
            return env["source"].readline()
        finally:
            env["last_line"] += 1

    def render(self, src, format=False):
        tokens = self.parse(src)
        env = self._init_env(src, tokens)
        out = self.render_tokens(tokens, env)
        return self.format(out) if format else out

    def render_cells(self, src):
        tokens = self.parse(src)
        prior = self._init_env(src, tokens)
        prior_token = None
        source = prior.pop("source")
        for block, next_token in self._walk_cells(tokens):
            env = self._init_env(src, block)
            env["source"], env["last_line"] = source, prior["last_line"]
            prior_token and block.insert(0, prior_token)
            yield self.render_tokens(block, env, next_token)
            print(env)
            prior, prior_token = env, next_token

    def render_tokens(self, tokens, env=None, stop=None):
        """render parsed markdown tokens"""
        target = StringIO()

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
                    colon_block=code.meta["colon_block"],
                    quoted_block=code.meta["quoted_block"],
                    last_indent=code.meta["last_indent"],
                )

                # format and print
                self.print(self.code_block(code, env), target)

        # handle anything left in the buffer
        self.print(self.non_code(env, stop), target)

        return target.getvalue()  # return the value of the target, a format string.

    def wrap_lines(self, lines, lead="", pre="", trail=""):
        """a utility function to manipulate a buffer of content line-by-line."""
        ws, any = "", False
        for line in lines:
            LL = len(line.rstrip())
            if LL:
                yield from (ws, lead, line[:LL])
                any, ws = True, line[LL:]
                lead = ""
            else:
                ws += line
        if any:
            yield trail
        yield ws

    def _init_env(self, src, tokens):
        env = dict(source=StringIO(src), last_line=0, min_indent=0, last_indent=0)
        for token in tokens:
            if token.type == "code_block":
                if env["min_indent"]:
                    env["min_indent"] = min(env["min_indent"], token.meta["min_indent"])
                else:
                    env["min_indent"] = token.meta["min_indent"]
        return env

    def _walk_cells(self, tokens):
        block = []
        for token in tokens:
            if token.type == "hr":
                if (len(token.markup) - token.markup.count(" ")) > self.cell_hr_length:
                    yield (list(block), token)
                    block.clear()
                    block.append(token)
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


def _code_lexer(state, start, end, silent=False):
    if state.sCount[start] - state.blkIndent >= 4:
        first_indent, last_indent, next, last_line = 0, 0, start, start
        while next < end:
            if state.isEmpty(next):
                next += 1
                continue
            if state.sCount[next] - state.blkIndent >= 4:
                begin = state.bMarks[next] + state.tShift[next]
                if state.srcCharCode[begin : begin + 3] == DOCTEST_CHARS:
                    break
                if not first_indent:
                    first_indent = state.sCount[next]
                last_indent, last_line = state.sCount[next], next
                next += 1
            else:
                break
        state.line = next
        token = state.push("code_block", "code", 0)
        token.content = state.getLines(start, next, 4 + state.blkIndent, True)
        token.map = [start, state.line]
        end_char = state.srcCharCode[state.eMarks[last_line] - 1]
        min_indent = min(
            state.sCount[i]
            for i in range(start, next)
            if not state.isEmpty(i) and state.sCount[i]
        )
        meta = dict(
            quoted_block=False,
            colon_block=False,
            first_indent=first_indent,
            last_indent=last_indent,
            min_indent=min_indent,
        )
        end_pos = state.eMarks[last_line] - 1
        if end_char == CONTINUATION_CHAR:
            end_char = state.srcCharCode[end_pos]
        if end_char == COLON_CHAR:
            meta["colon_block"] = True
        elif (end_char in QUOTES_CHARS) and end > 2:
            meta["quoted_block"] = all(
                map(end_char.__eq__, state.srcCharCode[end_pos - 2 : end_pos])
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

    if state.srcCharCode[start : start + 3] == DOCTEST_CHARS:
        indent, next = state.sCount[startLine], startLine + 1
        while next < end:
            if state.isEmpty(next):
                break
            if state.sCount[next] < indent:
                break
            begin = state.sCount[next]
            if state.srcCharCode[begin : begin + 3] == DOCTEST_CHARS:
                break
            next += 1

        state.line = next
        token = state.push("fence", "code", 0)
        token.info = "pycon"
        token.content = state.getLines(startLine, next, 0, True)
        token.map = [startLine, state.line]
        return True
    return False
