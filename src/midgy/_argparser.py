from argparse import ArgumentParser, BooleanOptionalAction

parser = ArgumentParser("midgy")
parser.add_argument(
    "-l",
    "--lang",
    "--language",
    default=None,
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
# parser.add_argument(
#     "-f",
#     "--fence",
#     dest="fenced_code_blocks",
#     default=None,
#     nargs="*",
#     help="include fenced code",
# )
parser.add_argument(
    "--doctest",
    dest="doctest_code_blocks",
    default=None,
    action="store_true",
    help="include doctest code blocks",
)
# parser.add_argument("-d", "--description", type=str, default=None, help="snippet description")
# parser.add_argument(
#     "-n",
#     "--name",
#     dest="var",
#     help="assign a variable name to the output",
#     default=None,
#     type=str,
# )
parser.add_argument(
    "-u",
    "--unsafe",
    dest="unsafe",
    help="template source before execution",
    default=False,
    action="store_true",
)

parser.add_argument(
    "-s",
    "--show",
    action="store_true",
    dest="show",
    default=None,
    help="""show the tangled source code""",
)
parser.add_argument(
    "-b",
    "--black",
    action="store_true",
    dest="format",
    default=None,
    help="""format the tangled source code""",
)
parser.add_argument(
    "--weave", action="store_true", dest="weave", help="""show the display""", default=True
)
parser.add_argument(
    "--lists",
    action="store_true",
    dest="lists",
    help="""don't translate markdown lists to python lists""",
    default=".-*",
)
# yaml uses these for lists
parser.add_argument(
    "-d",
    "--defs",
    action="store_true",
    dest="defs",
    help="""translate markdown definition lists to python dictionaries""",
    default=True,
)
parser.add_argument(
    "-n",
    "--name",
    type=str,
    dest="name",
    help="""name to store the source code as""",
    default=None,
)
parser.add_argument(
    "-w", "--no-weave", action="store_false", dest="weave", help="""hide the display"""
)
parser.add_argument(
    "-p", "--tokens", action="store_true", default=False, help="show parsed markdown tokens"
)
parser.add_argument("-t", "--unittest", action="store_false", default=True, help="test the code")
parser.add_argument(
    "-y", "--run", action="store_true", dest="run", help="""execute the source code""", default=True
)
parser.add_argument(
    "-x", "--no-run", action="store_false", dest="run", help="""hide the source code"""
)
parser.add_argument("-m", "--module", type=str, help="""a module to execute""")
parser.add_argument(
    "--md",
    action="store_false",
    help="""use the ipython markdown display instead of the html display""",
    dest="html",
    default=True,
)
parser.add_argument("-c", "--cmd", type=str, help="""a command to execute""")
parser.add_argument("file", nargs="*", type=str, help="a file to execute")


def run(*args):
    from .tangle import Tangle

    ns = Tangle.from_argv(*args)
