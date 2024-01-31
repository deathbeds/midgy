"""midgy translates (ie tangles) commonmark markdown to python code."""

__all__ = "Python", "md_to_python"
import sys

from .python import Python
from ._version import __version__

tangle = md_to_python = Python.code_from_string


def load_ipython_extension(shell):
    from ._ipython import load_ipython_extension

    load_ipython_extension(shell)


def unload_ipython_extension(shell):
    from ._ipython import unload_ipython_extension

    unload_ipython_extension(shell)


if "IPython" in sys.modules:
    import IPython
    from ._magics import load_ipython_extension as _load_ipython_extension

    _load_ipython_extension(IPython.get_ipython())
    del IPython, _load_ipython_extension
del sys
