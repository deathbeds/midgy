from io import StringIO
from pathlib import Path
from re import compile
from textwrap import indent

from markdown_it import MarkdownIt

BLANK, CONTINUATION, COLON, FENCE, SPACE = "", "\\", ":", "```", " "
QUOTES = "'''", '"""'
CELL_MAGIC, DOCTEST_LINE = compile("^\s*%{2}\S"), compile("^\s*>{3}\s+")
DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
DOCTEST_CHARS = DOCTEST_CHAR, DOCTEST_CHAR, DOCTEST_CHAR

def doctest(state, startLine, end, silent=False):
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


def code(state, start, end, silent=False):
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
        meta = dict(
            quoted_block=False,
            colon_block=False,
            first_indent=first_indent,
            last_indent=last_indent,
        )
        if end_char == CONTINUATION_CHAR:
            end_char = state.srcCharCode[state.eMarks[last_line] - 2]
        if end_char == COLON_CHAR:
            meta["colon_block"] = True
        elif end_char in QUOTES_CHARS and end > 2:
            meta["quoted_block"] = all(
                end_char.__eq__, state.srcCharCode[end - 3 : end]
            )
        token.meta.update(meta)
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
        self.renderer_cls, self.renderer = renderer, renderer()

    def initial_env(self, src):
        return dict(source=StringIO(src), target=StringIO(), last_line=0)

    def parse(self, src, env=None):
        """parse the source and return the markdown tokens"""
        if env is None:
            env = self.initial_env(src)
        return super().parse(src, env)

    def render(self, src, env=None):
        """render the source as translated python"""
        if CELL_MAGIC.match(src):
            return src
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
    quote_char = '"'

    def generic(self, env, next=None):
        body = super().generic(env, next)

        ref = env.get("reference_indent", 0)

        if env.get("quoted_block"):
            return indent(body, SPACE * ref)

        left = body.rstrip()

        if not left:
            return body

        # get states of the enclosing code blocks if there are any
        next_indent = next.meta["first_indent"] if next else 0
        prior_indent = env.get("last_indent", 0)
        colon = env.get("colon_block", False)
        spaces = prior_indent # compute extra spaces to apply

        if colon:
            # this is a python convention we apply when inside of the a colon block.
            if next_indent > prior_indent:
                # when the trailing indent is greater we prefer that
                spaces = next_indent
            else:
                # add post colon default spaces.
                spaces += 4

        # we're going to shuffle from lines to generic
        lines, generic = StringIO(left), StringIO()

        # this loop breaks at the first populated line.
        # it indents and quotes the first line then breaks.
        for line in lines:
            any = bool(line.lstrip())
            if any:
                print(SPACE * (spaces - ref), file=generic, end="")
                print(self.quote_char * 3, file=generic, end="")
            print(line, file=generic, end="")
            if any:
                break

        # add the rest of the lines to the generic bufffer
        # up until the last whitespace.
        for line in lines:
            print(line, file=generic, end="")

        # insert quotes before the white space
        print(self.quote_char * 3, file=generic, end="")
        if not next:
            # add a semi colon to the last string block to suppress that strings output
            print(";", file=generic, end="")

        # add the rest of the white space
        print(body[len(left) :], file=generic, end="")

        return generic.getvalue()

    def code_block(self, token, options, env):
        body = StringIO()
        # set the default reference indent as soon as we can.
        ref = env.setdefault("reference_indent", token.meta["first_indent"])

        # add the prior block of markdown
        print(self.generic(env, token), end="", file=body)

        for line in self.yieldlines(token.map[1], env):
            print(line[ref:], end="", file=body)

        env.update(
            colon_block=token.meta["colon_block"],
            quoted_block=token.meta["quoted_block"],
            last_indent=token.meta["last_indent"],
        )
        return body.getvalue()


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

    print(Columns(columns, **kwargs))


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
