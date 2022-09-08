"""public facing tools using midgy"""

from .py import Python, Renderer


def load_front_matter(x):
    x = x.strip()
    marker = x[0]
    if marker == "+":
        return load_toml(x.strip("+"))
    elif marker == "-":
        return load_yaml(x.strip("-"))
    raise ValueError(f"`{marker*3}` not recognized")


def load_toml(x):
    from tomli import loads

    return loads(x)


def _get_yaml_loader():
    loader = getattr(_get_yaml_loader, "loader", None)
    if loader:
        return loader
    try:
        from ruamel.yaml import safe_load as load
    except ModuleNotFoundError:
        try:
            from yaml import safe_load as load
        except ModuleNotFoundError:
            from json import loads as load
    _get_yaml_loader.loader = load
    return load


def load_yaml(x):
    return _get_yaml_loader()(x)


def md_to_python(body, renderer_cls=Python, *, _renderers={}):
    renderer = _renderers.get(renderer_cls)
    if renderer is None:
        renderer = _renderers[renderer_cls] = Renderer(renderer_cls=renderer_cls)

    return renderer.render(body)


def tangle_string(s, **kwargs):
    return md_to_python(s, **kwargs)


def tangle_file(path, **kwargs):
    return tangle_string(path.read_text(), **kwargs)


def iter_globs(*glob, recursive=False):
    from glob import glob as find

    for g in glob:
        yield from map(Path, find(g))


def format_black(body):
    from black import format_str, FileMode

    return format_str(body, mode=FileMode())


def show_rich(source, md=False, py=True, format=False, **kwargs):
    from rich import print
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.columns import Columns
    from rich.panel import Panel

    py = tangle_string(source)
    lineno = True

    if format:
        py = format_black(py)

    columns = []

    if md and py:
        columns.append(Panel(Syntax(source, "gfm", line_numbers=lineno), title="md"))
        lineno = not lineno
    elif md:
        columns.append(Markdown(source))

    if py:
        if format:
            lineno = True
        columns.append(Panel(Syntax(py, "python", line_numbers=lineno), title="py"))

    print(Columns(columns, **kwargs))
