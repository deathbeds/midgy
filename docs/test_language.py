from pathlib import Path
from pytest import mark
import midgy

HERE = Path(__file__).parent
source = (HERE / "language.md").read_text()

import midgy.tangle


def gen_tests(source):
    lines = source.splitlines()
    parser = midgy.tangle.Tangle()

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
                    name = parser.render_tokens(tokens[: n - 1], env, token).strip()
                    i = token.content
                if token.info == "python":
                    o = token.content

        if name:
            yield name, i, o


cases = list(gen_tests(source))
print(cases)


@mark.parametrize("n,i,o", cases, ids=[case[0] for case in cases])
def test_language(n, i, o):
    gen = midgy.Python().render(i)
    assert gen == o
