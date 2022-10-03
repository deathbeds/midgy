# tokenization

`midgy` uses `markdown-it-py` to tokenize markdown to CommonMark tokens
and extend that CommonMark grammar. the `midgy` language extends the following `markdown-it-py` tokens:

1. __shebang__ for historical purposes we add a token for the shebang line. it is always the first line of the document and indicates how to execute the document.

  > `midgy` documents will often begin with `#!/usr/bin/env midgy` to indicate that it can be executed.

2. __front matter__ is included because of its acceptance as convention in blogging. the shebang token is introduced as the only thing that can precede front matter.

3. __docstring__ tokens are added to indented code blocks. docstrings are literate programming convention introduced to python and we recognize this so authors have a natural convention for including tests in their programs.

4. __indented code__ blocks are modified to separate doctests from reference code.


[^mdast]: 
    we could use `mdast` as a specification for tokenizing markdown. the `markdown-it-py` module uses its own token representation.
[^lark]: 
    markdown grammars have ambiguities when parsing inline tokens, but block tokens are well defined. it could be possible to write an `ebnf` grammar for the blocks tokens. a grammar would be a great specification to target.
