from argparse import ArgumentParser, BooleanOptionalAction
from shlex import split


class Runner:
    @classmethod
    def run_magic(cls, line, cell=None):
        if cell is None:
            return cls.run_magic_line(line)
        return cls.run_magic_cell(line, cell)

    @classmethod
    def run_magic_line(cls, line):
        return

    @classmethod
    def run_magic_cell(cls, line, cell):
        from shlex import split, quote

        return cls.run_argv(split(line) + ["--cmd", quote(cell)[1:-1]])

    @classmethod
    def run_argv(cls, argv):
        return cls.run_ns(*parser.parse_known_args(argv))

    @classmethod
    def run_ns(cls, ns, argv):
        ns = vars(ns)
        run, display, file, module, cmd = (
            ns.pop(x, None) for x in ("run", "display", "file", "module", "cmd")
        )
        parser = cls.parser_from_ns(ns)
        if cmd:
            return cls.run_ns_cmd(parser, cmd, run, display)
        return

    @classmethod
    def parser_from_ns(cls, ns):
        from .tangle import Tangle

        lang = ns.pop("language", "python")
        cls = Tangle.cls_from_lang(lang)
        return cls(**ns)

    @classmethod
    def run_ns_cmd(cls, parser, cmd, run, display):
        from IPython import get_ipython

        src = parser.render(cmd)
        if display:
            print(src)

        if run:
            shell = get_ipython()
            co = shell.run_cell_async(cmd, transformed_cell=src, store_history=False)
            try:
                result = shell.loop_runner(co)
            except RuntimeError:
                import nest_asyncio
                nest_asyncio.apply()
                return cls.run_ns_cmd(parser, cmd, run, False) 
            

    @classmethod
    def run_ns_module(cls, argv):
        return

    @classmethod
    def run_ns_file(cls, argv):
        return


parser = ArgumentParser("midgy")
parser.add_argument(
    "-l",
    "--lang",
    "--language",
    default="python",
    type=str,
    dest="language",
    help="the target language",
)
parser.add_argument(
    "--string",
    dest="noncode_blocks",
    action="store_true",
    default=True,
    help="include non code markdown as strings",
)

parser.add_argument(
    "--comment",
    dest="noncode_blocks",
    action="store_false",
    default=True,
    help="exclude non code markdown as comments",
)
parser.add_argument(
    "-i",
    "--no-indent",
    dest="indented_code_blocks",
    action="store_false",
    default=True,
    help="exclude indented code blocks",
)
parser.add_argument(
    "-f",
    "--fence",
    dest="fenced_code_blocks",
    default=None,
    nargs="*",
    help="include fenced code",
)
parser.add_argument(
    "--doctest",
    dest="doctest_code_blocks",
    default=None,
    action="store_true",
    help="include doctest code blocks",
)
# parser.add_argument(
#     "-s",
#     "--set-var",
#     dest="var",
#     help="assign a variable name to the output",
#     default=None,
#     type=str,
# )
parser.add_argument(
    "-t",
    "--tangle",
    action="store_true",
    dest="display",
    default=None,
    help="""display the tangled source code""",
)
parser.add_argument(
    "-n", "--no-run", action="store_false", dest="run", help="""hide the source code"""
)
parser.add_argument("-m", "--module", type=str, help="""a module to execute""")
parser.add_argument("-c", "--cmd", type=str, help="""a command to execute""")

parser.add_argument("file", nargs="*", type=str, default=None, help="a file to execute")


def run(*args):
    from .tangle import Tangle

    Tangle.from_argv(*args)

import ast
def runner(source):
    module = compile(source, "", ast.PyCF_ONLY_AST)
    for node in module.body:
        co = compile(node, "", ast.Module([node], []))
        eval(co)
