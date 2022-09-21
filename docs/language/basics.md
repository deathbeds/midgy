## basic markdown to python translations

there are 3 flavors of literate programming available in `midgy`. 
we can interleave non-code with code found as: 
1. indented code blocks
2. code fences with specific `info` content
3. indented doctests when the `include_doctest` flag is enabled

-------------------------------------------------------

## tangling code with indented code blocks

the primary flavor of `midgy` literate programming uses indented code blocks.
content in between indented code blocks is treated as python blocks strings.
the samples below show some general interactions between non-code and indented code blocks.
 
*******************************************************

single markdown lines are single python strings

```markdown
a single line line of markdown is a python string.
```

```python
"""a single line line of markdown is a python string.""";
```

the semi-colon is appended to trailing block strings to suppress their output.

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
