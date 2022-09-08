from .md import Markdown, Renderer, SPACE
from textwrap import indent
from io import StringIO
from re import compile

ESCAPE = {x: "\\" + x for x in "'\""}
ESCAPE_PATTERN = compile("[" + "".join(ESCAPE) + "]")


def escape(x, char='"'):
    def match(m):
        return ESCAPE.get(m.group(0))

    return ESCAPE_PATTERN.sub(match, x)


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
        spaces = prior_indent  # compute extra spaces to apply

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
            print(escape(line), file=generic, end="")
            if any:
                break
        # add the rest of the lines to the generic bufffer
        # up until the last whitespace.
        for line in lines:
            print(escape(line), file=generic, end="")

        # insert quotes before the white space
        print(self.quote_char * 3, file=generic, end="")
        if not next:
            # add a semi colon to the last string block to suppress that strings output
            print(";", file=generic, end="")

        # add the rest of the white space
        print(body[len(left) :], file=generic, end="")

        return generic.getvalue()

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
        pre = env.setdefault("pre", StringIO())
        start, stop = token.map
        for i, line in enumerate(self.yieldlines(token.map[1], env)):
            if i == start:
                print(
                    "locals().update(__import__('midgy').load_front_matter(",
                    file=pre,
                    end="",
                )
                print(self.quote_char * 3, file=pre, end="")
            if i == (stop - 1):
                left = line.rstrip()
                print(escape(left), file=pre, end="")
                print(self.quote_char * 3, file=pre, end="")
                print("))", file=pre, end="")
                print(line[len(left) :], file=pre, end="")
            else:
                print(escape(line), file=pre, end="")

        return pre.getvalue()
