# markdown to python translations

`midgy` transpiles markdown to python using a minimal set of heuristics.
the sections below illustrate the translations from markdown to python.

-------------------------------------------------------

## basic markdown to python translations

by default, `midgy` translates markdown content to python strings.

*******************************************************

single markdown lines are single python strings

```markdown
a single line line of markdown is a python string.
```

```python
"""a single line line of markdown is a python string.""";
```

*******************************************************

a block of markdown lines are python block strings

```markdown
a paragraph with a list following:
* list item 1
* list item 2
```

```python
"""a paragraph with a list following:
* list item 1
* list item 2""";
```

*******************************************************

0-3 indents are treated as non-code

```markdown
   an indented markdown line
```

```python
"""   an indented markdown line""";
```

*******************************************************

at least 4 indents are raw python code

```markdown
    print("hello world")
```

```python
print("hello world")
```

*******************************************************

more than 4 indents are raw python code

```markdown
          print("hello world")
```

```python
print("hello world")
```

*******************************************************

code fences are treated as noncode

````markdown
```python
print("hello world")
```
````

```python
"""```python
print("hello world")
```""";
```

-------------------------------------------------------

## code and non-code

*******************************************************

code before markdown requires a dedent

```markdown
    x = "code before markdown"
a markdown paragraph after code
```

```python
x = "code before markdown"
"""a markdown paragraph after code""";
```

*******************************************************

code after markdown requires a blank line

```markdown
a markdown paragraph before code

    x = "code after markdown"
```

```python
"""a markdown paragraph before code"""

x = "code after markdown"
```

*******************************************************

triple double-quotes indicate explicit strings
    
```markdown
    """

a markdown paragraph
with lines

    """
```

```python
"""

a markdown paragraph
with lines

"""
```

*******************************************************

triple single-quotes indicate explicit strings
    
```markdown
    '''

a markdown paragraph
with lines

    '''
```

```python
'''

a markdown paragraph
with lines

'''
```
*******************************************************

markdown following a colon block (function) is indented
    
```markdown
        def f():
the docstring of the function f

        print(f())
```

```python
def f():
    """the docstring of the function f"""

print(f())
```

*******************************************************

markdown following a colon block (function) aligns to trailing code
    
```markdown
        def f():
the docstring of the function f

                        return 42
```

```python
def f():
                """the docstring of the function f"""

                return 42
```


*******************************************************

line continuations provide interoperability

```markdown
            foo =\
            \
line continuations assign this string to `foo`
```

```python
foo =\
\
"""line continuations assign this string to `foo`""";
```


-------------------------------------------------------

## front matter

`midgy` permits `yaml` and `toml` front matter.

*******************************************************

triple + indicates toml front matter

```markdown
+++
+++
```

```python
locals().update(__import("midgy").front_matter.load("""+++
+++"""))
```

*******************************************************

triple - indicates yaml front matter
    
```markdown
---
---
```

```python
locals().update(__import("midgy").front_matter.load("""---
---"""))
```



*******************************************************

only shebang tokens can precede front matter

```markdown
#!/usr/bin/env midgy
---
---
```

```python
#!/usr/bin/env midgy
locals().update(__import("midgy").front_matter.load("""---
---"""))
```

*******************************************************

non-shebang tokens cancel front matter

```markdown
a short paragraph
---
---
```

```python
"""a short paragraph
---
---""";
```
*******************************************************

exclude frotn matter from parsing

```markdown
+++
["*"]
include_front_matter = false
+++
```

```python
# +++
# ["*"]
# include_front_matter = false
# +++
```


-------------------------------------------------------

## doctest

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

    >>> assert 'this is a doctest\
    ... because it is indented'""";
```

*******************************************************

`include_doctest` flag includes doctest inputs in code

```markdown
+++
["*"]
include_doctest = true
include_front_matter = false
+++

    >>> print("a doctest")
```

```python
# +++
# ["*"]
# include_doctest = true
# include_front_matter = false
# +++

print("a doctest")
```

