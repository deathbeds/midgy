import builtins, re
from dataclasses import dataclass, field
from doctest import ELLIPSIS
from functools import lru_cache
from io import StringIO
from pathlib import Path
from shlex import split
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic
from jinja2 import Environment

from midgy.language.python import Python
from midgy.types import HTML, Css, Script, Markdown

from ._ipython import run_ipython

from .weave import quick_doctest, weave_argv
from ._argparser import parser
from traitlets import (
    Any,
    CInt,
    CUnicode,
    Dict,
    HasTraits,
    CBool,
    Instance,
    List,
    Callable,
    Type,
    Unicode,
    Bool,
)


class Tangle(HasTraits):
    from .containers import Containers

    noncode_blocks = CBool().tag(config=True)
    code_blocks = List(CUnicode, ["indent"]).tag(config=True)
    language = CUnicode("python").tag(config=True)
    parser = Instance(Python, (), {}).tag(config=True)
    enabled = Bool(True)
    depth = CInt()

    def __enter__(self):
        self.depth += 1

    def __exit__(self, *e):
        self.depth -= 1

    def render_lines(self, lines):
        if self.depth:
            return lines
        return self.parser.render_lines(lines)

    def eval(self, code):
        return run_ipython(self.parser.render(code))


is_midgy = re.compile(r"\s*%{2}(pidgy|midgy)?\s+")


def midgy_transform(lines):
    from IPython import get_ipython

    for i, line in enumerate(lines):
        if any(line.strip()):
            break
    if is_midgy.match(line):
        return ["\n"] * i + get_ipython().tangle.render_lines(lines[i + 1 :])
    return lines


class Weave(HasTraits):
    enabled = Bool(True)
    display = Any(None)
    unittest = CBool(False)
    doctest_flags = Any(ELLIPSIS)
    display_cls = Callable(Markdown)

    def post_run_cell(self, result):
        from IPython.display import display, Markdown
        from IPython import get_ipython

        shell = get_ipython()
        print(self.enabled)
        if self.enabled:
            cell = result.info.raw_cell
            for line in StringIO(cell):
                line = line.strip()
                if line:
                    # if line.startswith(("%%",)):
                    #     break
                    
                    shell.templates[tpl := "{shell.last_execution_result.info.cell_id}.md"] = cell
                    display(shell.weave.display_cls(
                        shell.env.get_template(tpl).render()
                    ))
                    if (
                        shell.weave.unittest
                        and "doctest" not in shell.tangle.code_blocks
                    ):
                        quick_doctest(cell)

                return


def get_parser(x):
    from importlib.metadata import entry_points

    return next(iter(entry_points(group="midgy", name=x.lstrip("."))), None)


@magics_class
class TangleMagic(Magics):
    @cell_magic
    def tangle(self, line, cell=""):
        from shlex import quote

        cmd = split(line) + ["--cmd", "\n" + cell]
        with self.shell.tangle:
            try:
                return weave_argv(cmd, magic=True)
            except SystemExit:
                pass

class DictLoader(__import__("jinja2").DictLoader):
    def __setitem__(self, key, value):
        self.mapping[key] = value
    def __getitem__(self, key):
        return self.mapping[key]

@lru_cache(1)
def get_environment():
    from jinja2 import Environment, ChoiceLoader, FileSystemLoader

    return Environment(loader=ChoiceLoader([
        FileSystemLoader(Path())
    ]))

# def render_pug(lines):
#     from IPython import get_ipython
#     shell = get_ipython()
#     shell.envir
import jinja2.ext, os
class MarkdownExt(jinja2.ext.Extension):
    options = {}
    file_extensions = '.md'
    def preprocess(self, source, name, filename=None):
        loader = self.env.loader
        try:
            loader = loader.app.jinja_loader # we're in a Flask app
        except AttributeError:
            pass
        if hasattr(loader, 'searchpath') and len(loader.searchpath):
            self.options["basedir"] = loader.searchpath[0]

        if not name or (name and os.path.splitext(name)[1] not in self.file_extensions):
            return source
        from IPython import get_ipython
        shell = get_ipython()
        return get_ipython().tangle.parser.parser.render(source, env=shell._markdown_env)

# this extension is installed by default when midgy is imported in an ipython context
def load_ipython_extension(shell):
    """initialize the tangle and weave magics for explicit use cases."""
    if shell:
        from jinja2 import Environment

        shell.user_ns.setdefault("shell", shell)
        if not shell.has_trait("tangle"):
            from markdown_it import MarkdownIt
            shell.add_traits(tangle=Instance(Tangle, (), {}))
            shell.add_traits(fence_methods=Instance(dict, (), {}))
            shell.add_traits(markdown=Instance(MarkdownIt, (), {}))
            shell.fence_methods = shell.tangle.parser.fence_methods
            shell.markdown_to_html = shell.tangle.parser.parser.render
            shell.markdown = shell.tangle.parser.parser
        if not shell.has_trait("weave"):
            shell.add_traits(weave=Instance(Weave, (), {}))
        if not shell.has_trait("environment"):
            from .environment import load_ipython_extension
            load_ipython_extension(shell)
            # shell.add_traits(environment=Instance(Environment, (), {}))
            # shell.env = environment
            # # shell.env.globals = shell.user_global_ns
            # # shell.env.globals.update(vars(builtins))
            # shell.add_traits(templates=Instance(DictLoader, ({},), {}))
            # shell.env.loader.loaders.append(shell.templates)
            
            # import pypugjs
            # shell.env.add_extension("pypugjs.ext.jinja.PyPugJSExtension")                        
            # # def visitInclude(self, node):
            # #     self.buf.append('{% include ' + node.path + ' %}')
            # #     # there are probably attrs and shit to care about

            # # pypugjs.ext.jinja.Compiler.visitInclude = visitInclude 
            
            
            # pypugjs.register_filter("md")(shell.tangle.parser.parser.render)
            # # pypugjs.register_filter("md")(shell.tangle.parser.parser.render)
            # shell.tangle.parser.fence_methods["pug"] = "midgy._magics:_pug_fence"
            
        if not shell.has_trait("_markdown_env"):
            shell.add_traits(_markdown_env=Dict({}))
        for t in (HTML, Css, Script, Markdown):
            shell.user_ns[t.__name__] = t

        shell.register_magics(TangleMagic(shell))
        magic = shell.magics_manager.magics["cell"]["tangle"]
        shell.magics_manager.magics["cell"][""] = magic
        if midgy_transform not in shell.input_transformer_manager.line_transforms:
            shell.input_transformer_manager.line_transforms.insert(0, midgy_transform)
        if post_run_cell not in shell.events.callbacks["post_run_cell"]:
            shell.events.register("post_run_cell", post_run_cell)
            
def _pug_fence(lines):
    from IPython import get_ipython
    from IPython.display import HTML
    shell = get_ipython()
    return HTML(shell.env.from_string(shell.env.extensions["pypugjs.ext.jinja.PyPugJSExtension"].preprocess(
        lines, shell.last_execution_result.info.cell_id
    )).render({**vars(builtins), **shell.user_ns}))
            
            

def post_run_cell(result):
    from IPython.display import display, Markdown, HTML
    from IPython import get_ipython

    shell = get_ipython()
    cell = result.info.raw_cell
    if shell.weave.enabled:
        for line in (buffer := StringIO(cell)):
            line = line.lstrip()
            if not line: 
                continue
            if is_midgy.match(line):
                tpl = F"{result.info.cell_id}.md"
                shell.templates[tpl] = "".join(buffer)
                for line in StringIO(shell.templates[tpl]):
                    if line.lstrip():
                        data = shell.env.get_template(tpl).render({**shell.user_ns, **vars(builtins)})
                        # if shell.weave.display_cls is HTML:
                        #     data = shell.tangle.parser.parser.render(data)
                        display({"text/html": data}, metadata={"jinja:Template": {tpl: shell.templates[tpl]}}, raw=True)
                    break
                if shell.weave.unittest and "doctest" not in shell.tangle.code_blocks:
                    quick_doctest(cell)
                return 
            return