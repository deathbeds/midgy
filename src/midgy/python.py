"""the Python class that translates markdown to python code"""

from dataclasses import dataclass, field
from io import StringIO
from .render import Renderer, escape

__all__ = "Python", "md_to_python"
SP, QUOTES = chr(32), ('"' * 3, "'" * 3)


@dataclass
class Python(Renderer):
    """a line-for-line markdown to python translator"""

    # include markdown as docstrings of functions and classes
    include_docstring: bool = True
    # include docstring as a code block
    include_doctest: bool = False
    # include front matter as a code block
    include_front_matter: bool = True
    # include markdown in that code as strings, (False) uses comments
    include_markdown: bool = True
    # code fence languages that indicate a code block
    include_code_fences: list = field(default_factory=["python"].copy)

    front_matter_loader = '__import__("midgy").front_matter.load'
    _quote_char = chr(34)

    def code_block(self, token, env):
        """return raw indent code block"""
        if self.include_indented_code:
            yield from self.non_code(env, token)
            yield from (line[env["min_indent"] :] for line in super().code_block(token, env))
            self.get_updated_env(token, env)

    def comment(self, block, indent_or_env):
        """comment a block of code"""
        if not isinstance(indent_or_env, int):
            indent_or_env = self.get_computed_indent(indent_or_env)
        yield from self.wrap_lines(block, pre=SP * indent_or_env + "# ")

    def doctest_comment(self, token, env):
        """comment a doctest block"""
        yield from self.non_code(env, token)
        yield self.comment(self.get_block(env, token.map[1]), env)

    def doctest_code(self, token, env):
        """return a doctest as a block of code.

        * inputs are returned as code
        * output is commented"""
        yield from self.non_code(env, token)
        for line in self.get_block(env, token.meta["input"][1]):
            # remove first 4 characters ">>> " and "... "
            right = line.lstrip()
            yield line[env["min_indent"] : len(line) - len(right)] + right[4:]
        if token.meta["output"]:
            yield self.comment(self.get_block(env, token.meta["output"][1]), env)
        self.get_updated_env(token, env)

        env.update(colon_block=False, quoted_block=False, continued=False)

    def fence_pycon(self, token, env):
        """comment, render, or string a block of doctest code

        pycon is the pygments identifier to the python console"""
        if self.include_doctest:
            yield from self.non_code(env, token)
            yield from self.doctest_code(token, env)
        elif self.include_docstring and self.include_markdown:
            return
        else:
            yield from self.doctest_comment(token, env)

    def fence_python(self, token, env):
        """return a modified code fence that identifies as code"""

        if token.info in self.include_code_fences:
            # clear the cache of any non-code in the buffer
            yield from self.non_code(env, token)
            # comment out the leading line of code fences
            yield from self.comment(
                self.get_block(env, token.map[0] + 1), token.meta["first_indent"]
            )
            # return the actual code
            yield from self.get_block(env, token.map[1] - 1)
            # comment out the last line of code fences
            yield from self.comment(self.get_block(env, token.map[1]), token.meta["last_indent"])
            # push token metadata to the parser
            self.get_updated_env(token, env)

    def format(self, body):
        """blacken the python"""
        from black import FileMode, format_str

        return format_str(body, mode=FileMode())

    def front_matter(self, token, env):
        """comment, codify, or stringify blocks of front matter"""
        if self.include_front_matter:
            trail = self._quote_char * 3
            lead = f"locals().update({self.front_matter_loader}(" + trail
            trail += "))"
            body = self.get_block(env, token.map[1])
            yield from self.wrap_lines(body, lead=lead, trail=trail)
        else:
            yield from self.comment(self.get_block(env, token.map[1]), env)

    def get_computed_indent(self, env):
        """compute the indent for the first line of a non-code block."""
        next = env.get("next_code")
        next_indent = next.meta["first_indent"] if next else 0
        spaces = prior_indent = env.get("last_indent", 0)
        if env.get("colon_block", False):  # inside a python block
            if next_indent > prior_indent:
                spaces = next_indent  # prefer greater trailing indent
            else:
                spaces += 4  # add post colon default spaces.
        return max(spaces, env["min_indent"]) - env["min_indent"]

    def non_code(self, env, next=None):
        """stringify or comment non code blocks"""
        if env.get("quoted_block", False):
            yield from self.wrap_lines(super().non_code(env, next))
        elif self.include_markdown:
            yield from self.non_code_block_string(env, next)
        else:
            yield from self.non_code_comment(env, next)

    def non_code_block_string(self, env, next=None):
        """codify markdown as a block string"""
        body = super().non_code(env, next)
        lead = trail = self._quote_char * 3
        indent = self.get_computed_indent(env)
        # add quotes + trailing text on the whole block
        trail += "" if next else ";"
        yield from self.wrap_lines(
            map(escape, body),
            lead=SP * indent + lead,
            trail=trail,
            continuation=env.get("continued") and "\\" or "",
        )

    def non_code_comment(self, env, next=None):
        """comment non code blocks"""
        yield self.comment(super().non_code(env, next), env)

    def shebang(self, token, env):
        """return the shebang line"""
        yield from self.wrap_lines(self.get_block(env, token.map[1]))

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
                        yield pre
                        yield l[:-1] + continuation + l[-1]
                yield from (pre, lead, line[:LL])
                any, ws = True, line[LL:]
                lead = ""
            else:
                ws += line
        if any:
            yield trail
        if continued:
            for i, line in enumerate(StringIO(ws)):
                yield from (i and pre or "", line[:-1], i and "\\" or "", line[-1])
        else:
            yield ws


tangle = md_to_python = Python.code_from_string
