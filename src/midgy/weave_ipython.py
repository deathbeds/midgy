from dataclasses import field
from shlex import split
from numpy import isin
from .tangle import BLOCK, Tangle
from ._argparser import parser
class Weave:
    source: str = None
    parser: Tangle = None
    out: str = None
    env: dict = field(default_factory=dict)
    tokens: list = None

def weave(cmd=None, file=None, module=None, run=True, display=False, language="python", **kwargs):
    parser = Tangle.cls_from_lang(language)
    self = Weave(source=cmd, parser=parser)

    self.tokens = self.parser.parse(self.source, self.env)
    self.out = Block(self.parser.render_tokens(self.tokens, self.env, self.source))

    if display and run:
        print(self.out)
        
    if run:
        return self.parser.eval(self.out)
    return self.out

def weave_argv(argv):
    ns, extra = parser.parse_known_args(ns)
    return weave(**vars(ns), extra=extra)


class Block(str):
    __repr__ = str.__str__