from io import StringIO
from .weave import quick_doctest, weave_argv

NEST_ASYNC = None


def post_run_cell(result):
    from IPython.display import display, Markdown
    from IPython import get_ipython

    shell = get_ipython()
    if shell.weave.enabled:
        cell = result.info.raw_cell
        for line in StringIO(cell):
            line = line.strip()
            if line:
                if line.startswith(("%%",)):
                    break

                display(shell.weave.display_cls(cell))
                if shell.weave.unittest and "doctest" not in shell.tangle.code_blocks:
                    quick_doctest(cell)

            return


def load_ipython_extension(shell):
    shell.input_transformers_cleanup.insert(0, shell.tangle.render_lines)
    shell.events.register("post_run_cell", post_run_cell)


def unload_ipython_extension(shell):
    if shell.has_trait("tangle"):
        try:
            shell.input_transformers_cleanup.remove(shell.tangle.parser.render_lines)
            shell.events.unregister("post_run_cell", post_run_cell)
        except ValueError:
            pass


def run_ipython(source, _retry=False):
    global NEST_ASYNC
    from asyncio import get_event_loop
    from IPython import get_ipython
    from IPython.core.interactiveshell import ExecutionResult, ExecutionInfo
    from inspect import CO_COROUTINE
    from ast import Expression, Module, PyCF_ALLOW_TOP_LEVEL_AWAIT, PyCF_ONLY_AST, Expr
    from uuid import uuid1

    shell = get_ipython()

    filename = str(uuid1()) + ".py"
    source = shell.transform_cell(source)
    interactivity = "none" if source.rstrip().endswith(";") else shell.ast_node_interactivity
    module = compile(source, filename, "exec", PyCF_ONLY_AST)
    module = shell.transform_ast(module)
    result = ExecutionResult(ExecutionInfo(source, False, False, False, filename))

    if NEST_ASYNC is None:
        import nest_asyncio

        nest_asyncio.apply()
        NEST_ASYNC = True

    get_event_loop().run_until_complete(
        shell.run_ast_nodes(
            module.body,
            filename,
            compiler=shell.compile,
            result=result,
            interactivity=interactivity,
        )
    )
    return
