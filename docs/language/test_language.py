from pathlib import Path
from pytest import mark
import midgy

HERE = Path(__file__).parent

import midgy.render


def gen_tests():
    parser = midgy.render.Renderer()
    for file in HERE.glob("*.md"):
        source = file.read_text()
        lines = source.splitlines()
        for cell in parser.render_cells(source):
            if not cell.lstrip().startswith("*"):
                continue
            cell = "".join(cell.splitlines(True)[1:])
            tokens = parser.parse(cell)
            if not tokens:
                continue

            name, i, o = None, None, None
            env = parser._init_env(cell, tokens)
            for n, token in enumerate(tokens):
                if token.type == "fence":
                    if token.info == "markdown":
                        i = token.content
                    if token.info == "python":
                        o = token.content
            name = get_description(tokens)
            if name:
                yield (file.stem, name), (i, o)

def get_description(tokens):
    for token in tokens:
        if token.type == "paragraph_open":
            continue
        elif token.type == "inline":
            desc = token.content
            continue
        elif token.type == "paragraph_close":
            return desc
        break



cases = dict(gen_tests())


@mark.parametrize("f,n", cases)
def test_language(f, n):
    i, o = cases[f, n]
    gen = midgy.Python().render(i)
    assert gen == o
