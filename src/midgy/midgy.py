from cmath import tan
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from re import compile
from textwrap import dedent, indent

from markdown_it import MarkdownIt

BLANK, CONTINUATION, COLON, FENCE, SPACE = "", "\\", ":", "```", " "
QUOTES = "'''", '"""'
CELL_MAGIC, DOCTEST_LINE = compile("^\s*%{2}\S"), compile("^\s*>{3}\s+")
DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
_RE_BLANK_LINE = compile(r"^\s*\r?\n")


def field(default=None, description=None, **metadata):
    from dataclasses import field

    param = {callable(default) and "default_factory" or "default": default}
    if description:
        metadata["description"] = description
    return field(metadata=metadata or None, **param)


def doctest(state, startLine, end, silent=False):
    """a markdown-it-py plugin for doctests

    doctest are a literate programming convention in python that we
    include in the pidgy grammar. this avoids a mixing python and doctest
    code together."""
    start = state.sCount[startLine]

    # if it's indented more than 3 spaces, it should be a code block
    if (start - state.blkIndent) >= 4:
        return False

    if all(map(DOCTEST_CHAR.__eq__, state.srcCharCode[start : start + 3])):
        indent, next = state.sCount[startLine], startLine + 1
        while next < end:
            if state.isEmpty(next):
                break
            if state.sCount[next] < indent:
                break
            begin = state.sCount[next]
            if all(map(DOCTEST_CHAR.__eq__, state.srcCharCode[begin : begin + 3])):
                break
            next += 1

        state.line = next
        token = state.push("doctest", "code", 0)
        token.content = state.getLines(startLine, next, 0, True)
        token.map = [startLine, state.line]
        return True
    return False


def code(state, start, end, silent=False):
    if state.sCount[start] - state.blkIndent >= 4:
        leading, next, quoted, colon = 0, start, False, False
        while next < end:
            if state.isEmpty(next):
                next += 1
                continue
            here = state.sCount[next]
            if all(map(DOCTEST_CHAR.__eq__, state.srcCharCode[here : here + 3])):
                break
            elif state.sCount[next] - state.blkIndent >= 4:
                if not leading:
                    leading = state.sCount[next]
                trailing = state.sCount[next]
                last_char = state.eMarks[next] - 1
                continued = state.srcCharCode[last_char] == CONTINUATION_CHAR
                length = state.eMarks[next] - (state.sCount[next])
                if continued:
                    last_char -= 1
                if continued and quoted and length == 1:
                    pass
                else:
                    colon = state.srcCharCode[last_char] == COLON_CHAR
                    quoted = state.srcCharCode[last_char] in QUOTES_CHARS
                    if quoted:
                        quoted = (
                            state.srcCharCode[last_char - 2 : last_char]
                            == (state.srcCharCode[last_char],) * 2
                        )
                    else:
                        quoted = False
                next = last = next + 1
            else:
                break
        state.line = last
        token = state.push("code_block", "code", 0)
        token.content = state.getLines(start, last, 4 + state.blkIndent, True)
        token.map = [start, state.line]
        token.meta.update(
            leading=leading,
            trailing=trailing,
            continued=continued,
            colon=colon,
            quotes=quoted,
        )
        return True
    return False


class Renderer(MarkdownIt):
    """the base renderer for translating markdown input"""

    def __init__(self, *args, **kwargs):
        renderer = kwargs.pop("renderer_cls", Markdown)
        super().__init__(*args or ("gfm-like",), **kwargs)
        self.block.ruler.before("code", "doctest", doctest)
        self.block.ruler.disable("code")
        self.block.ruler.after("doctest", "code", code)

        # self.block.ruler.before("code", "doctest", doctest)
        # instantiate the renderer_cls
        self.renderer_cls, self.renderer = renderer, renderer()

    def parse(self, src, env=None):
        """parse the source and return the markdown tokens"""
        if env is None:
            env = dict(vars(Env(source=StringIO(src))))

        return super().parse(src, env)

    def render(self, src, env=None):
        """render the source as translated python"""
        if CELL_MAGIC.match(src):
            return src
        if env is None:
            env = dict(vars(Env(source=StringIO(src))))

        return super().render(src, env)

    def render_lines(self, src):
        """a shim that includes the tangler in the ipython transformer"""
        return self.render("".join(src)).splitlines(True)


class Markdown:
    """a renderer_cls to be used with a Renderer"""

    def generic(self, env, next=None):
        return (
            "".join(env["source"]) if next is None else self.readlines(next.map[0], env)
        )

    def walk(self, tokens, options, env):
        for token in tokens:
            if hasattr(self, token.type):
                yield self.generic(env, token)
                yield getattr(self, token.type)(token, options, env)
        else:
            yield self.generic(env)

    def render(self, tokens, options, env):
        body = StringIO()
        for block in self.walk(tokens, options, env):
            body.writelines(block)
        return body.getvalue()

    def readline(self, env):
        try:
            return env["source"].readline()
        finally:
            env["last_line"] += 1

    def readlines(self, stop, env):
        """read multiple lines until you want to stop"""
        s = StringIO()
        while env["last_line"] < stop:
            s.writelines(self.readline(env))
        return s.getvalue()


@dataclass
class Env:
    """the rendering environment for the markdown it rendered"""

    @dataclass
    class IndentState:
        """the indent state relative to a markdown block    .

        the diagram below show the refenerce, trailing, and leading indents relative
        to a markdown block. the indents for the markdown need to be computed relative
        to the enclosing code blocks.

        reference CODECODECODECODECODECODECODECODE
        trailing  CODECODECODECODECODECODECODECODE

        MMMMMMDDDDDDDDDMMMMMMDDDDDDDDDMMMMMMDDDDDDDDD
        MMMMMMDDDDDDDDDMMMMMMDDDDDDDDDMMMMMMDDDDDDDDD

        leading        CODECODECODECODECODECODECODE
                CODECODECODECODECODECODECODE"""

        reference: int = field(
            0, "The first indent of the first line of code in a document"
        )
        trailing: int = field(0, "The indent of last code line before a markdown block")
        leading: int = field(0, "The indent of last code line before a markdown block")

    @dataclass
    class LastCharacterState:
        """the first non-blank character before a markdown block can change how the
        rendering step behaves. these conditions let us define markdown in python
        variables and write docstrings with markdown"""

        colon: bool = field(False, "The code before the markdown ends with `:`")
        quotes: bool = field(
            False, "The code before the markdown ends with triple quotes"
        )

    source: StringIO = field(None, "input code being translated")
    last_line: int = field(0, "the last code line visited")
    indents: IndentState = field(IndentState)
    chars: LastCharacterState = field(LastCharacterState)
    terminal_character: str = field(
        BLANK, "trailing character after the non-code block"
    )


DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}

# an instance of this class is used to transform markdown to valid python
# in the ipython extension. the python conversion is constrained by being
# a line for line transformation using indent code blocks (not code fences)
# as references for translating the markdown to valid python objects.

# the choice of indented code over code fences allows for more implicit interleaving
# of code and narrative.
class Python(Markdown):
    """a line-for-line markdown to python renderer"""

    markdown_is_block_string = True
    docstring_block_string = True

    def indent(self, input, i=0, prefix=""):
        """indent an input"""
        return indent(input, SPACE * i + prefix)

    def quote(self, input, env, i=0):
        """quote a string which requires the environment state"""
        return self._get_quoted(input, i, env)

    def comment(self, input, i=0):
        """comment an input"""

        return self.indent(input, i, "# ")

    def get_noncode_indent(self, env):
        return (
            self._get_noncode_indent(env["indents"], env["chars"])
            - env["indents"].reference
        )

    # this method is defined by the reusable markdown parent
    def generic(self, env, next=None):
        """process a generic block of markdown text."""

        indents, chars = env["indents"], env["chars"]
        if next is None:
            env["terminal_character"] = ";"

        else:
            if not indents.reference:
                indents.trailing = indents.reference = next.meta["leading"]
            indents.leading = next.meta["leading"]

        input, indent = super().generic(env, next), self.get_noncode_indent(env)

        if chars.quotes:
            # when we find quotes in code around a markdown block we don't augment the string.
            input = self.indent(input, indent)
        elif self.markdown_is_block_string:
            # augment a non-code markdown block as quoted string
            input = self.quote(input, env, indent)
        else:
            input = self.comment(input, indent)

        return self.indent(input, indents.reference)

    def code_block(self, token, options, env):
        """update the state block when code is found."""
        indents, chars = env["indents"], env["chars"]

        # update the trailing indent
        indents.trailing = token.meta["trailing"]

        # measure if there is a preceding colon indicating a python block indent
        chars.colon = token.meta["colon"]

        # measure if triple quotes exist around the surround code block
        chars.quotes = token.meta["quotes"]

        # read the lines pertaining to the raw code.
        return self.readlines(token.map[1], env)

    def render(self, tokens, options, env):
        return dedent(super().render(tokens, options, env))

    @staticmethod
    def _get_noncode_indent(indents, chars, **_):
        """compute the current indent based on the enclosing blocks"""
        if chars.quotes:  # then we require no adjustment
            return indents.reference
        elif chars.colon:
            return max(indents.trailing + 4, indents.leading)
        elif indents.leading >= indents.trailing:
            return indents.leading
        return indents.trailing

    @staticmethod
    def _get_quoted(input, indent=0, env=None):
        """heuristics that quote a non-code block as a string."""

        input = dedent(input)
        quote = QUOTES[QUOTES[0] in input]
        l, r = input.lstrip(), input.rstrip()
        if not (l or r):  # we have a blank string
            return input
        begin, end = input[: len(input) - len(l)], input[len(r) :]
        return (  # recombine all of the parts into quoted python
            begin  # leading whitespace1
            + SPACE * indent  # computed indent
            + quote  # enter block string
            + get_escaped_string(
                input[len(input) - len(l) : len(r)], quote[0]
            )  # code body
            + quote  # exit block string
            + env["terminal_character"]  # computed trailing character
            + end  # trailing whitespace
        )


def md_to_python(body, renderer_cls=Python, *, _renderers={}):
    renderer = _renderers.get(renderer_cls)
    if renderer is None:
        renderer = _renderers[renderer_cls] = Renderer(renderer_cls=renderer_cls)

    return renderer.render(body)


def tangle_string(s, **kwargs):
    return md_to_python(s, **kwargs)


def tangle_file(path, **kwargs):
    return tangle_string(path.read_text(), **kwargs)


def iter_globs(*glob, recursive=False):
    from glob import glob as find

    for g in glob:
        yield from map(Path, find(g))
            


def format_black(body):
    from black import format_str, FileMode

    return format_str(body, mode=FileMode())


def show_rich(source, md=False, py=True, format=False, **kwargs):
    from rich import print
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.columns import Columns
    from rich.panel import Panel

    py = tangle_string(source)
    lineno = True

    if format:
        py = format_black(py)

    columns = []

    if md and py:
        columns.append(Panel(Syntax(source, "gfm", line_numbers=lineno), title="md"))
        lineno = not lineno
    elif md:
        columns.append(Markdown(source))

    if py:
        if format:
            lineno = True
        columns.append(Panel(Syntax(py, "python", line_numbers=lineno), title="py"))

    print(Columns(columns,   **kwargs))

def main():
    from sys import argv
    
    for path in iter_globs(*argv[1:]):
        show_rich(path.read_text(), md=True, format=True, title=str(path))

    
def arguments():
    from argparse import ArgumentParser

    parser = ArgumentParser("midgy", description="convert markdown to python code")
    sub = parser.add_subparsers()
    show = sub.add_parser("show")
    run = sub.add_parser("run")
    convert = sub.add_parser("convert")

    run.add_argument("-i", "--input", help="input file or globs to execute.")

    show.add_argument("-m", "--md", action="store_true")
    show.add_argument("-p", "--py", action="store_false")

    return parser


def load_ipython_extension(shell):
    from traitlets import Instance

    def tangle(line, cell):
        print(shell.tangle.render(cell))

    def parse(line, cell):
        print(shell.tangle.parse(cell))

    shell.add_traits(tangle=Instance(Renderer, (), kw=dict(renderer_cls=Python)))
    shell.input_transformer_manager.cleanup_transforms.insert(
        0, shell.tangle.render_lines
    )
    shell.register_magic_function(tangle, "cell")
    shell.register_magic_function(parse, "cell")


def unload_ipython_extension(shell):
    if shell.has_trait("tangle"):
        shell.input_transformer_manager.cleanup_transforms = list(
            filter(
                shell.tangle.render_lines.__ne__,
                shell.input_transformer_manager.cleanup_transforms,
            )
        )


def get_escaped_string(object, quote='"'):
    from re import subn

    return subn(r"%s{1,1}" % quote, "\\" + quote, object)[0]

if __name__ == "__main__":
    main()