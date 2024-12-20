"""transform markdown to python
"""

from collections import deque
from dataclasses import dataclass, field
from functools import wraps
from importlib.metadata import EntryPoint
from io import StringIO
from itertools import pairwise, zip_longest
from re import sub
from subprocess import check_output
from textwrap import dedent
from ..tangle import Markdown, SP

LOAD_FENCE = """__import__("importlib").metadata.EntryPoint(None, "{}", None).load()"""


@dataclass
class Python(Markdown, type="text/x-python", language="ipython3"):
    """transform markdown to python code

    * a line-for-line transformation from md to py
    * characters are added, not removed **
    * the doctest literate programming style is supported for source code or testing

    **: doctest must modify source to work in midgy
    """

    COMMENT_MARKER = "# "
    STRING_MARKER = ['"""', '"""']
    CONTINUE_MARKER = "\\"
    TERMINAL_MARKER = ";"
    YAML = "yaml"  # yaml library we use, users may have different preferences.
    TOML = "tomli"  # toml library we use, users may have different preferences.

    # these entry point style references map to functiosn that code load string syntaxes
    fence_methods = dict(
        ini="midgy.front_matter:get_ini",
        cfg="midgy.front_matter:get_ini",
        json="json:loads",
        json5="json5:loads",
        yaml=f"{YAML}:safe_load",
        yml=f"{YAML}:safe_load",
        toml=f"{TOML}:loads",
        front_matter="midgy.front_matter:load",
        css="midgy.types:Css",
        html="midgy.types:HTML",
        markdown="midgy.types:Markdown",
        javascript="midgy.types:Script",
        graphviz="midgy.types:Dot",
        dot="midgy.types:Dot",
        md="midgy.types:Markdown",
        lisp="midgy.types:Hy.eval",
        hy="midgy.types:Hy.eval",
    )
    fenced_code_blocks: list = field(
        default_factory=["python", "python3", "ipython3", "ipython", ""].copy
    )
    include_quote_parenthesis: bool = field(default=True)
    link_iframes: bool = True
    front_matter_variable: str = "page"
    include_magic: bool = True
    hr_split: str = "_"

    def hr(self, token, env):
        if token.markup[0] in self.hr_split:
            yield from self.noncode_block(env, token)
            yield from self.noncode_block(env, token.map[1])

    def code_block(self, token, env):
        """render an ipython code block"""
        if token.meta.get("is_doctest"):
            if self.doctest_code_blocks:
                # include the doctest input block as code in the program
                yield from self.code_doctest(token, env)
        elif self.indented_code_blocks:
            # yield formatted non-code as string or comment
            yield from self.noncode_block(env, token)
            block = self.generate_block_lines(env, token.map[1])
            if self.include_magic and token.meta.get("is_magic"):
                # yield code formatted python code that invokes a ipython magic
                yield from self.cell_magic(token, block, env)
                self.update_env(token, env, last_indent=env.get("last_indent"))
            else:
                # the default dedents the code block to align code blocks
                yield from self.generate_dedent_block(block, env["min_indent"])
                self.update_env(token, env)

    def code_doctest(self, token, env):
        """format a markdown doctest into valid code.

        the input is included in the program and the output is commented out."""

        block = self.generate_block_lines(env, token.meta["input"][1])

        # normalize the input statement by dedenting & removing the 4 prefixes chars ">>> ", "... "
        block = self.generate_dedent_block(block, token.meta["min_indent"] + 4)
        indent = SP * self.get_indent(env)

        # indent the input block to align with the implicit indent
        yield from map(indent.__add__, block)
        if token.meta["output"]:
            block = self.generate_block_lines(env, token.meta["output"][1])
            block = self.generate_dedent_block(block, token.meta["min_indent"])
            # export the output blocks as comments so they do no interact with the program
            yield from map(indent.__add__, self.generate_comment(block, token, env))
        self.update_env(token, env, indented=False, quoted=False, continued=False)

    def cell_magic(self, token, block, env):
        """render a cell magic on a buffer that starts at the cell magic line"""
        first = next(block)
        prog = first.strip().lstrip("%")

        try:
            prog, *args = prog.split(maxsplit=1)
        except ValueError:
            # no whitespace to split
            args = ()

        min_indent = token and token.meta.get("min_indent") or 0
        yield SP * self.get_indent(env)

        # write the first line of the cell magic, the same transform IPython makes
        yield f"""get_ipython().run_cell_magic("{prog}", "{args and args[0] or ''}", """

        # we might have to worry about line continuations, that is not considered yet.
        # comment out the original line so we retain the undisturbed source
        yield f"# {first}"

        # write the cell body as a block string stripping the right most whitespace
        cell = "".join(self.generate_dedent_block(block, min_indent))
        left = cell.rstrip()

        # triple block quotes around cell
        yield from (self.STRING_MARKER[0], self.escape(left), self.STRING_MARKER[0])
        # close the magic method caller and write the trailing whitespace
        yield from (")", cell[len(left) :])

    @staticmethod
    def escape(str):
        return str.replace("\\", r"\\").replace('"', r"\"")

    def eval(self, tangled):
        from .._ipython import run_ipython

        return run_ipython(tangled)

    def fence(self, token, env):
        """dispatch different renderings of code fences."""
        if "~" not in token.markup:
            # tilde fences do not tangle. maybe make this configurable
            if token.meta.get("is_doctest"):
                if self.doctest_code_blocks:
                    yield from self.fence_doctest(token, env)
                    raise NotImplementedError()
            elif self.fenced_code_blocks:
                lang = self.get_lang(token)
                # format the prior non-code
                yield from self.noncode_block(env, token)
                if lang in self.fenced_code_blocks:
                    # render fence as python code
                    yield from self.fence_code(token, env)
                else:
                    # render fence as block string
                    yield from self.fence_noncode(token, env)
            else:
                return
            yield ""

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

    def fence_doctest(self, token, env):
        """render code fence as python code"""
        # we can't do this yet because we haven't parsed the doctest info.
        yield from ()

    def fence_noncode(self, token, env):
        """render a fence as a block string with an optional caller method"""
        yield SP * self.get_indent(env)

        # fence method are functions applied to block string in a fence like json, toml, tomli
        method = self.get_fence_method(token)
        if method:
            # methods are preceded a parenthesis allowing for line contination
            yield f"({method}"

        # parenthesis are used to group strings together and allow for methods to called on the block string.
        # group and comment out the first line of the fence dashes
        yield "( # "
        yield from self.generate_block_lines(env, token.map[0] + 1)

        # quote and escape the string block
        yield self.STRING_MARKER[0]
        block = self.generate_block_lines(env, token.map[1] - 1)
        block = self.generate_dedent_block(block, token.meta.get("min_indent"))
        yield from map(self.escape, block)
        yield self.STRING_MARKER[1]

        # close the fence group and comment out the last fence dashes
        # this syntax restricuts from using line continuations like indented code blocks
        # if the comment were dropped then we could use continuations
        yield ")"
        if method:
            yield ")"
        yield " # "
        rest = self.generate_block_lines(env, token.map[1])
        if token.meta["next_code"] is None:
            last = next(rest)
            yield last[:-1]
            if not method:
                # show anything with a method directly
                # ipython test for semi colon at the end of any line,
                # not the end of a valid python expression
                yield ";"
            yield last[-1]
        else:
            yield from rest

    def front_matter(self, token, env):
        """render front matter as python code with an optional variable name"""
        yield from self.generate_block_lines(env, token.map[0])
        if self.front_matter_variable:
            # the front matter variable is the name assign the parsed front matter.
            # we choose the default name because of its conventions in static site generators
            # like jekyll.
            yield self.front_matter_variable
            yield " = "

        # comment out first and last line while applying a parsing method to string
        yield from self.fence_noncode(token, env)

    def display_iframes(self, tokens, env, target):
        print(
            f"""__import__("importlib").import_module("midgy._ipython").iframes('''""",
            sep="",
            end="",
            file=target,
        )
        for line in self.generate_block_lines(env):
            print(line, sep="", end="", file=target)
        print("""''');""", sep="", end="", file=target)

    def parse(self, source, env=None):

        tokens = super().parse(source, env)
        if env is None:
            env = self.initialize_env(source, tokens)
        self.postlex(tokens, env)
        return tokens

    def postlex(self, tokens, env):
        code = None
        for token in tokens[::-1]:
            token.meta["next_code"] = code
            if self.is_code_block(token):
                code = token

    def generate_tokens(self, tokens, env=None, src=None, stop=None, target=None):
        """generate lines of python code transformed from mardown."""
        right = src.lstrip()
        if right.startswith(("%%",)):
            for part in self.cell_magic(None, StringIO(right), env):
                print(part, sep="", end="", file=target)
            return

        if self.link_iframes and is_urls(tokens):
            self.display_iframes(tokens, env, target)
            return

        # work backwards through the tokens to associated code blocks and non-code blocks

        # work forward through the tokens to render the python code
        for token, next in zip_longest(tokens, tokens[1:]):
            env["next"] = next
            if self.is_code_block(token):
                env["next_code"] = token
            for line in self.render_token(token, env):
                print(line, file=target, sep="", end="")
            env["last"] = token

        # handle still in the buffer as a non code block
        for line in self.noncode_block(env, stop):
            print(line, file=target, sep="", end="")

    def get_fence_method(self, token):
        """map the code fence info to python method"""
        lang = self.get_lang(token)
        method = self.fence_methods.get(lang, lang)
        if ":" in method:
            return LOAD_FENCE.format(method)
        return ""

    def get_indent(self, env):
        """compute the indent for non-code blocks based on bounding code block conditions."""

        # the default indent is the dendet of the last line of a preceeding code block
        # or the minimum indent of the entire block
        indent = max(env.get("last_indent", env.get("min_indent")), env.get("min_indent"))
        if env.get("indented"):
            # indent blocks from a colon from an if, def, or class statement.
            # this computation makes it possible to use markdown as docstrings
            # or trigger condition magics that weren't possible otherwise.
            next_code = env.get("next_code")
            if next_code:
                # if there is a following code block
                next_indent = next_code.meta["first_indent"]
                if next_indent > indent:
                    # prefer the next code blocks indent if it is greater than the default
                    indent = next_indent
                else:
                    # otherwise add 4 spaces to avoid syntax errors
                    indent += 4
            else:
                indent += 4
        return indent - env.get("min_indent")

    def get_lang(self, token):
        """transform the fence info to the language it represents"""
        lang = token.info.split(maxsplit=1)
        return lang and lang[0] or ""

    def is_code_block(self, token):
        """is the token a code block entry"""
        is_code = super().is_code_block(token)
        if not is_code:
            if token.meta.get("is_doctest"):
                return self.doctest_code_blocks
            # test for PYCON fence
        return is_code

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

    def generate_comment(self, block, token, env, *, prepend="", **kwargs):
        if self.comment_prefix_line:
            yield from self.noncode_whitespace(env)
            pre = SP * self.generate_env_indent(env, token) + self.COMMENT_MARKER
            for line in block:
                if line.strip():
                    yield from self.noncode_whitespace(env)
                    yield self.COMMENT_MARKER + " "
                    yield line
                else:
                    env["whitespace"].write(line)
            yield from self.noncode_whitespace(env)
        else:
            self.generate_wrapped_lines(
                block, lead=(prepend or "") + self.COMMENT_MARKER[0], trail=self.COMMENT_MARKER[1]
            )

    def noncode_string(
        self,
        block,
        next_block,
        env,
        paren=True,
        hanging=False,
        prepend="",
        append="",
        whitespace=True,
    ):
        """generate a block string from a noncode block"""
        block = "".join(block)
        if env.get("hanging"):
            block = StringIO(block)
            try:
                block = next(block) + dedent("".join(block))
            except StopIteration:
                return
        else:
            block = dedent(block)
        body = block.lstrip()
        start = len(block) - len(body)
        body = body.rstrip()
        end = start + len(body)
        env["whitespace"].write(block[:start])

        # yield any preceeding whitespace
        body = self.escape(body)
        if body:
            yield from self.noncode_whitespace(env)
            # noncode blocks that end with a line continuation
            # will continue that line to the next code or non-code block
            env["continued"] = body.endswith("\\")
            if env["continued"]:
                body = body[:-2]
            # place tight quote before the block string body
            if not env.get("hanging"):
                yield SP * self.get_indent(env)
            yield prepend
            if not env.get("quoted"):
                if paren and self.include_quote_parenthesis:
                    yield "("
                yield self.STRING_MARKER[0]
        yield from StringIO(body)
        if body:
            # place tight quote after the block string body
            if not env.get("quoted"):
                yield self.STRING_MARKER[1]
                if paren and self.include_quote_parenthesis:
                    yield ")"
            yield append
            if next_block is None:
                yield ";"
        env["whitespace"].write(block[end:])
        if whitespace:
            yield from self.noncode_whitespace(env)

    def noncode_whitespace(self, env):
        indent = self.get_indent(env)
        env["whitespace"].seek(0)
        for line in env["whitespace"]:
            if line.endswith("\n"):
                if env.get("continued"):
                    yield SP * indent
                    yield "\\"
                yield "\n"
        env["whitespace"] = StringIO()

    def render_lines(self, source):
        return self.render("".join(source)).splitlines(True)

    def update_env(self, token, env, **kwargs):
        env["quoted"] = token.meta.get("is_quoted")
        env["continued"] = token.meta.get("is_continued")
        env["indented"] = token.meta.get("is_indented")
        env["last_indent"] = token.meta.get("last_indent", env["last_indent"])
        env["next_code"] = token.meta.get("next_code")
        env.update(kwargs)


def is_urls(tokens):
    """determine if a string is a block of urls from markdown it tokens."""

    for token in tokens:
        if token.type in {"paragraph_open", "paragraph_close"}:
            continue
        if token.type == "inline":
            for child, next_child in pairwise(token.children + [None]):
                if child.type == "link_open":
                    if next_child and next_child.type == "text":
                        continue
                elif child.type == "text":
                    if next_child and next_child.type == "link_close":
                        continue
                    return False
                elif child.type in {"softbreak", "link_close"}:
                    continue
            continue
        return False
    return True
