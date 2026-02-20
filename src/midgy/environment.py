import jinja2, argparse, shlex, json, builtins
from pathlib import Path
from functools import partial
from dataclasses import dataclass

MARKDOWN_EXT = ".md", ".mdown"

def visitInclude(self, node):
    if md := node.path.lower().endswith(MARKDOWN_EXT):
        self.buf.append("{% filter md %}")
    self.buf.append("{% include '")
    self.buf.append(node.path)
    self.buf.append("'%}")
    if md:
        self.buf.append("{% endfilter %}")

def _pug_fence(lines):
    from IPython import get_ipython
    from IPython.display import HTML
    from .types import Pug
    import builtins
    shell = get_ipython()
    return Pug("".join(lines))
    
    
def get_pypugjs(shell, env):
    import textwrap
    try:
        import pypugjs
    except:
        return
    env.add_extension(pypugjs.ext.jinja.PyPugJSExtension)
    env.filters["pug"] = pugjs
    def md_filter(text, ast=None):
        return env.filters["md"](textwrap.dedent(text))

    pypugjs.register_filter("md")(md_filter)
    shell.tangle.parser.fence_methods["pug"] = "midgy.environment:_pug_fence"
    pypugjs.ext.jinja.Compiler.visitInclude = visitInclude


class DictLoader(jinja2.DictLoader):
    def __setitem__(self, key, value):
        self.mapping[key] = value

    def __getitem__(self, key):
        return self.mapping[key]


def get_environment(shell, markdown_env={}):
    import jinja2.ext, pypugjs.ext.jinja, markdown_it, traitlets

    env = Environment(loader=jinja2.ChoiceLoader([jinja2.FileSystemLoader("")]), cache_size=0)
    env.filters["md"] = partial(shell.tangle.parser.parser.render, env=markdown_env)
    try:
        get_pypugjs(shell, env)
    except ModuleNotFoundError:
        pass
    return env


def pugjs(source):
    from IPython import get_ipython
    import textwrap

    shell = get_ipython()
    return shell.env.from_string(
        shell.env.extensions["pypugjs.ext.jinja.PyPugJSExtension"].preprocess(
            textwrap.dedent(source), "this.pug"
        ),
        None,
        MarkdownAwareTemplate,
    ).render({**vars(builtins), **shell.user_ns})


def load_ipython_extension(shell):
    import traitlets

    env = get_environment(shell)
    loader = DictLoader({})
    shell.add_traits(
        env=traitlets.Instance("jinja2.Environment", (), {}, default_value=env),
        templates=traitlets.Instance(DictLoader, ({},), {}, default_value=loader),
    )
    shell.templates = loader
    shell.env = env
    env.extend(templates=shell.templates)
    env.loader.loaders.append(shell.templates)
    shell.register_magic_function(template_magic, "line_cell", "template")
    assert shell.templates is shell.env.templates is shell.env.loader.loaders[1], (
        "DictLoader templates where initialized out of order"
    )


class MarkdownAwareTemplate(jinja2.Template):
    def render(self, *args, **kwargs):
        text = super().render(*args, **kwargs)
        if (self.name or self.filename or "").endswith(".md"):
            text = self.environment.filters["md"](text)
        return text


class Environment(jinja2.Environment):
    template_class = MarkdownAwareTemplate

    def from_string(
        self, source, globals=None, template_class=None, filename=None, name=None
    ):
        gs = self.make_globals(globals)
        cls = template_class or self.template_class
        return cls.from_code(
            self, self.compile(source, name=name, filename=filename), gs, None
        )


parser = argparse.ArgumentParser("template")
parser.add_argument("name", nargs="?", default=None)
parser.add_argument("-w", "--write", action="store_true")


def template_magic(line, cell):
    from IPython import get_ipython, HTML
    from pathlib import Path
    from IPython.display import display

    shell = get_ipython()
    args = parser.parse_args(shlex.split(line))
    if cell is None:
        return
    if args.name:
        if cell is None:
            return shell.env.get_template(args.name).render(globals())
        shell.env.dict_loader.mapping[args.name] = cell
        if args.write:
            Path(args.name).write_text(cell)
        return display(
            HTML(shell.env.from_string(cell, name=line).render(globals())),
            metadata={"jinja2:Template": {line: cell}},
        )
    return shell.env.get_template(line).render(globals())


@dataclass(unsafe_hash=True)
class NotebookLoader(jinja2.BaseLoader):
    path: Path

    def get_templates_from_notebook_output(self):
        return get_templates_from_notebook_output(self.path)

    def list_templates(self):
        return list(self.get_templates_from_notebook_output())

    def get_source(self, environment, name, globals=None):
        t = Path(self.path).stat().st_mtime
        try:
            return (
                self.get_templates_from_notebook_output()[name],
                name,
                lambda: Path(self.path).stat().st_mtime == t,
            )
        except:
            raise jinja2.TemplateNotFound("can't find template")


def get_templates_from_notebook_output(file):
    from functools import reduce
    from itertools import chain

    cells = json.loads(Path(file).read_text()).get("cells", [])
    templates = reduce(
        dict.__or__,
        filter(
            bool,
            (
                output.get("metadata", {}).get("jinja2:Template")
                for output in chain.from_iterable(
                    cell.get("outputs", "") for cell in cells
                )
            ),
        ),
        {},
    )
    return templates