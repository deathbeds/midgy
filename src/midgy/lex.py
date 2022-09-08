"""custom markdown-it-py lexers for the pidgy language"""
from re import compile
BLANK, CONTINUATION, COLON, FENCE, SPACE = "", "\\", ":", "```", " "
QUOTES = "'''", '"""'
CELL_MAGIC, DOCTEST_LINE = compile("^\s*%{2}\S"), compile("^\s*>{3}\s+")
DOCTEST_CHAR, CONTINUATION_CHAR, COLON_CHAR, QUOTES_CHARS = 62, 92, 58, {39, 34}
DOCTEST_CHARS = DOCTEST_CHAR, DOCTEST_CHAR, DOCTEST_CHAR


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


SHEBANG = compile("^#!(?P<interpreter>\S+)\s+(?P<command>\S*)")


def _shebang_lexer(state, startLine, endLine, silent):
    auto_closed = False
    start = state.bMarks[startLine] + state.tShift[startLine]
    maximum = state.eMarks[startLine]
    src_len = len(state.src)

    # our front matter allows for indents and can occur at positions
    # other than 0
    # this should filter out non-front matter
    if start:
        return False

    m = SHEBANG.match(state.src[start:maximum])
    if not m:
        return False

    parent = state.parentType
    line_max = state.lineMax

    # this will prevent lazy continuations from ever going past our end marker
    state.lineMax = startLine

    token = state.push("shebang", "", 0)
    token.hidden = True
    token.content = state.getLines(startLine, startLine + 1, 0, True)
    token.block = True

    state.parentType = parent
    state.lineMax = line_max
    state.line = startLine + 1
    token.map = [startLine, state.line]

    return True


def _front_matter_lexer(state, startLine, endLine, silent):
    auto_closed = False
    start = state.bMarks[startLine] + state.tShift[startLine]
    maximum = state.eMarks[startLine]
    src_len = len(state.src)

    # our front matter allows for indents and can occur at positions
    # other than 0
    # this should filter out non-front matter

    if state.sCount[startLine]:
        return False

    if state.tokens:
        if len(state.tokens) > 1:
            return False
        if state.tokens[-1].type != "shebang":
            return False

    markup = None
    if state.srcCharCode[start] == ord("-"):
        markup = "-"
    elif state.srcCharCode[start] == ord("+"):
        markup = "+"
    else:
        return False

    if state.srcCharCode[start + 1 : maximum] != tuple(map(ord, (markup, markup))):
        return False

    # Search for the end of the block
    nextLine = startLine

    while True:
        nextLine += 1
        if nextLine >= endLine:
            return False

        start = state.bMarks[nextLine] + state.tShift[nextLine]
        maximum = state.eMarks[nextLine]

        if start < maximum and state.sCount[nextLine] < state.blkIndent:
            break

        if ord(markup) != state.srcCharCode[start]:
            continue

        if state.sCount[nextLine] - state.blkIndent >= 4:
            continue

        if state.srcCharCode[start + 1 : maximum] == tuple(map(ord, (markup, markup))):
            auto_closed = True
            nextLine += 1
            break

    parent = state.parentType
    line_max = state.lineMax
    state.parentType = "container"

    # this will prevent lazy continuations from ever going past our end marker
    state.lineMax = nextLine

    token = state.push("front_matter", "", 0)
    token.hidden = True
    token.markup = markup
    token.content = state.getLines(startLine, nextLine, 0, True)
    token.block = True

    state.parentType = parent
    state.lineMax = line_max
    state.line = nextLine
    token.map = [startLine, state.line]

    return True


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