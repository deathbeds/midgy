# doctest

*******************************************************

by default doctests are not included in code.

```markdown
>>> this is a blockquote
... with a trailing paragraph
and is not a doctest

    >>> assert 'this is a doctest\
    ... because it is indented'
```

```python
""">>> this is a blockquote
... with a trailing paragraph
and is not a doctest

    >>> assert \'this is a doctest\
    ... because it is indented\'""";
```

*******************************************************

`include_doctest` flag includes doctest inputs in code

```markdown
+++
[py]
include_doctest = true
include_front_matter = false
+++

    >>> print("a doctest")
```

```python
# +++
# [py]
# include_doctest = true
# include_front_matter = false
# +++

print("a doctest")
```

----------------------------------------------------------

## using explicit `doctest` for literate programming

it is possible to program in doctests.  


[pymarkdown]: https://github.com/mrocklin/pymarkdown