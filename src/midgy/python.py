"""a minimal conversion from markdown to python code based on indented code blocks"""

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent, indent

from .tangle import DedentCodeBlock

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

    markdown_is_block_string: bool = True
    docstring_block_string: bool = True
    quote_char: str = chr(34)
    include_doctest_input: bool = False
    front_matter_loader = '__import("midgy").front_matter.load'

    def code_block(self, token, env):
        yield from super().code_block(token, env)
        left = token.content.rstrip()
        continued = left.endswith("\\")
        left = continued and left.rstrip("\\") or left
        env["colon_block"] = left.endswith(":")
        env["quoted_block"] = left.endswith(QUOTES)

    def comment(self, body, env):
        return indent(dedent("".join(body)), SP * self._compute_indent(env) + "# ")

    def doctest_comment(self, token, env):
        yield from self.non_code(env, token)
        yield (self.comment(self.get_block(env, token.map[1]), env),)

    def doctest_code(self, token, env):
        ref = env["min_indent"]
        # yield self.non_code(env, token)
        pre_len = 2
        spaces = self._compute_indent(env)
        yield from self.non_code(env, token)
        for line in self.get_block(env, token.meta["input"][1]):
            right = line.lstrip()
            yield SP * spaces + right[4:]
        if token.meta["output"]:
            yield self.comment(self.get_block(env, token.meta["output"][1]), env)

    def fence_pycon(self, token, env):
        if self.include_doctest_input:
            yield from self.doctest_code(token, env)
        elif self.docstring_block_string and self.markdown_is_block_string:
            return
        else:
            yield from self.doctest_comment(token, env)

    def front_matter(self, token, env):
        trail = self.quote_char * 3
        lead = f"locals().update({self.front_matter_loader}(" + trail
        trail += "))"
        body = self.get_block(env, token.map[1])
        yield from self.wrap_lines(body, lead=lead, trail=trail)

    def non_code(self, env, next=None):
        if env.get("quoted_block", False):
            yield from super().non_code(env, next)
        elif self.markdown_is_block_string:
            yield from self.non_code_block_string(env, next)
        else:
            yield from self.non_code_comment(env, next)

    def non_code_block_string(self, env, next=None):
        body = super().non_code(env, next)
        trail = self.quote_char * 3
        lead = SP * self._compute_indent(env) + trail
        trail += "" if next else ";"
        yield from self.wrap_lines(body, lead=lead, trail=trail)

    def non_code_comment(self, env, next=None):
        yield self.comment(super().non_code(env, next), env)

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

    def format(self, body):
        """blacken the python"""
        from black import format_str, FileMode

        return format_str(body, mode=FileMode())


md_to_python = Python.code_from_string
