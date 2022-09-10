"""render markdown as python code

this module exports the renderer class to transform
markdown into python using midgy conventions."""

from functools import partial
from .md import Markdown, MarkdownIt, SPACE
from io import StringIO
from re import compile

ESCAPE = {x: "\\" + x for x in "'\""}
ESCAPE_PATTERN = compile("[" + "".join(ESCAPE) + "]")

escape = partial(ESCAPE_PATTERN.sub, lambda m: ESCAPE.get(m.group(0)))


class Config:
    markdown_is_block_string = True
    docstring_block_string = True
    quote_char = '"'
    formatter = None


class Python(Markdown, Config):
    """a line-for-line markdown to python renderer"""

    def compose_generic_string(self, body, env, lead="", pre="", trail=""):
        """compose a block string.
        lead applies to first line, pre applies to every other line,"""

        left = body.rstrip()
        if not left:
            return body
        old, new = StringIO(left), StringIO()
        if lead:
            # this loop breaks at the first populated line.
            # it indents and quotes the first line then breaks.
            for line in old:
                any = bool(line.lstrip())
                any and print(lead, file=new, end="")
                print(escape(line), file=new, end="")
                if any:
                    break

        for line in old:
            print(pre, escape(line), file=new, end="", sep="")
        print(trail, body[len(left) :], file=new, end="")
        return new.getvalue()

    def compute_generic_lead(self, env, next=None):
        next_indent = next.meta["first_indent"] if next else 0
        spaces = prior_indent = env.get("last_indent", 0)
        if env.get("colon_block", False):  # inside a python block
            if next_indent > prior_indent:
                spaces = next_indent  # prefer greater trailing indent
            else:
                spaces += 4  # add post colon default spaces.
        return SPACE * (spaces - env.get("reference_indent", 0))

    def generic(self, env, next=None):
        body = super().generic(env, next)
        if env.get("quoted_block"):
            return body
        trail = self.quote_char * 3
        lead = self.compute_generic_lead(env, next) + trail
        if not next:
            trail += ";"
        return self.compose_generic_string(body, env, lead=lead, trail=trail)

    def doctest(self, token, options, env):
        if self.docstring_block_string:
            return

    def shebang(self, token, options, env):
        return "".join(self.yieldlines(token.map[1], env))

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

    def front_matter(self, token, options, env):
        trail = self.quote_char * 3
        lead = "locals().update(__import__('midgy').load_front_matter(" + trail
        trail += "))"
        body = "".join(self.yieldlines(token.map[1], env))
        return self.compose_generic_string(body, env, lead=lead, trail=trail)


def md_to_python(body, renderer_cls=Python, *, _renderers={}):
    renderer = _renderers.get(renderer_cls)
    if renderer is None:
        renderer = _renderers[renderer_cls] = MarkdownIt(renderer_cls=renderer_cls)

    return renderer.render(body)
