"""a minimal conversion from markdown to python code based on indented code blocks"""

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent, indent

from .render import DedentCodeBlock, escape

__all__ = "Python", "md_to_python"
SP, QUOTES = chr(32), ('"' * 3, "'" * 3)

# the Python class translates markdown to python with the minimum number
# of modifications necessary to have valid python code. midgy will:
## add triple quotes to make python block strings of markdown blocks
## escape quotes in markdown blocks
## add indents to conform with python concepts
# overall spaces, quotes, unicode escapes will be added to your markdown source.
@dataclass
class Python(DedentCodeBlock):
    """a line-for-line markdown to python translator"""

    include_docstring: bool = True
    include_doctest: bool = False
    include_front_matter: bool = True
    include_markdown: bool = True
    extend_continuations: bool = True
    include_code_fences: list = field(default_factory=list)

    front_matter_loader = '__import__("midgy").front_matter.load'
    quote_char = chr(34)

    def code_block(self, token, env):
        if self.include_indented_code:
            yield from super().code_block(token, env)
            left = token.content.rstrip()
            continued = left.endswith("\\")
            if continued:
                left = left[:-1]
            env.update(
                colon_block=left.endswith(":"),
                quoted_block=left.endswith(QUOTES),
                continued=continued,
            )

    def code_fence_block(self, token, env):
        yield self.comment(self.get_block(env, token.map[0] + 1), env)
        yield from self.get_block(env, token.map[1] - 1)
        yield self.comment(self.get_block(env, token.map[1]), env)
        env.update(colon_block=False, quoted_block=False, continued=False)

    def comment(self, body, env):
        return indent(dedent("".join(body)), SP * self._compute_indent(env) + "# ")

    def doctest_comment(self, token, env):
        yield from self.non_code(env, token)
        yield (self.comment(self.get_block(env, token.map[1]), env),)

    def doctest_code(self, token, env):
        ref = env["min_indent"]
        yield from self.non_code(env, token)
        for line in self.get_block(env, token.meta["input"][1]):
            right = line.lstrip()
            yield line[ref : len(line) - len(right)] + right[4:]
        if token.meta["output"]:
            yield self.comment(self.get_block(env, token.meta["output"][1]), env)
        env.update(colon_block=False, quoted_block=False, continued=False)

    def fence_pycon(self, token, env):
        if self.include_doctest:
            yield from self.doctest_code(token, env)
        elif self.include_docstring and self.include_markdown:
            return
        else:
            yield from self.doctest_comment(token, env)

    def format(self, body):
        """blacken the python"""
        from black import FileMode, format_str

        return format_str(body, mode=FileMode())

    def front_matter(self, token, env):
        if self.include_front_matter:
            trail = self.quote_char * 3
            lead = f"locals().update({self.front_matter_loader}(" + trail
            trail += "))"
            body = self.get_block(env, token.map[1])
            yield from self.wrap_lines(body, lead=lead, trail=trail)
        else:
            yield self.comment(self.get_block(env, token.map[1]), env)

    def non_code(self, env, next=None):
        if env.get("quoted_block", False):
            yield from super().non_code(env, next)
        elif self.include_markdown:
            yield from self.non_code_block_string(env, next)
        else:
            yield from self.non_code_comment(env, next)

    def non_code_block_string(self, env, next=None):
        body = super().non_code(env, next)
        trail = self.quote_char * 3
        lead = SP * self._compute_indent(env) + trail
        trail += "" if next else ";"
        yield from self.wrap_lines(
            map(escape, body),
            lead=lead,
            trail=trail,
            continuation=self.extend_continuations and env.get("continued") and "\\" or "",
        )

    def non_code_comment(self, env, next=None):
        yield self.comment(super().non_code(env, next), env)

    def render_tokens(self, tokens, env=None, stop=None, src=None):
        return dedent(super().render_tokens(tokens, env=env, stop=stop, src=src))

    def shebang(self, token, env):
        yield "".join(self.get_block(env, token.map[1]))

    def _compute_indent(self, env):
        """compute the indent for the first line of a non-code block."""
        next = env.get("next_code")
        next_indent = next.meta["first_indent"] if next else 0
        spaces = prior_indent = env.get("last_indent", 0)
        if env.get("colon_block", False):  # inside a python block
            if next_indent > prior_indent:
                spaces = next_indent  # prefer greater trailing indent
            else:
                spaces += 4  # add post colon default spaces.
        return spaces - env.get("min_indent", 0)


tangle = md_to_python = Python.code_from_string


@dataclass
class FencedPython(Python):
    """a line-for-line markdown to python translator"""

    include_code_fences: list = field(default_factory=["python", ""].copy)


tangle = md_to_python = Python.code_from_string
