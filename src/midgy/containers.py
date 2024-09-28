"""renderers for lists and definition lists in python"""

from dataclasses import dataclass
import midgy, markdown_it, re
from .language.python import Python


@dataclass
class Lists(Python):
    def escape(self, body):
        """escape"""
        body = re.compile("^(\s{,3}([\-\+\*\:]|[0-9]+[.\)]?)\s{,4})*").sub("", body)
        return super().escape(body)

    # the hyphen is a default choice for lists because they appear isomorphic to yaml lists
    # the parenthesis is a less common ordered list format in markdown meaning is a little more explicit
    # than the period indiciator.
    list_items: str = "-)"

    def update_env(self, token, env):
        super().update_env(token, env)
        env["hanging"] = False

    def bullet_list_open(self, token, env):
        env["comment"] = env.get("comment") or token.markup not in self.list_items
        if token.markup not in self.list_items:
            return
        if not (parent := token.meta.get("parent")):
            yield from self.noncode_block(env, token.map[0] - 1)
        if (prior := token.meta.get("prior")) and (open := prior.meta.get("open")).meta.get(
            "parent"
        ) is parent:
            yield "+"
        else:
            yield " " * self.get_indent(env)

    def bullet_list_close(self, token, env):
        if token.markup not in self.list_items:
            return
        if not token.meta["open"].meta.get("parent"):
            env["comment"] = False

    def list_item_open(self, token, env):
        if token.markup not in self.list_items:
            return
        if token.meta.get("first"):
            yield from self.noncode_block(env, token.map[0] - 1, comment=True)
            yield "(["
            env["continued"] = False
        env.update(comment=False, hanging=True)

    def list_item_close(self, token, env):
        if token.markup not in self.list_items:
            return
        last = token.meta.get("last")
        if comment := env.get("comment"):
            yield last and "])" or ","
        yield from self.noncode_block(
            env, (open := token.meta.get("open")).map[1], whitespace=False, comment=comment
        )
        if not comment:
            yield last and "])" or ","
        if open.meta.get("parent"):
            env["comment"] = bool(token.meta.get("last"))
        env.update(hanging=False)

    ordered_list_open, ordered_list_close = bullet_list_open, bullet_list_close

    def postlex(self, tokens, env):
        parents, cleared, swaps = [], [], []
        prior = None, None
        # go backwards through the tokens looking for lists
        for i, token in enumerate(tokens[::-1], 1):
            if token.type == "code_block":
                if prior[1] is not None:
                    if prior[0].type == "list_item_close" and prior[1].type == "bullet_list_close":
                        prior[1].meta["end_code"] = prior[0].meta["end_code"] = token
                        swaps.append(i)
            if token.markup not in self.list_items:
                continue
            prior = token, prior[0]
            match token:
                case markdown_it.token.Token(type="bullet_list_close" | "ordered_list_close"):
                    parents.append((token, []))
                    if cleared:
                        if (parent := cleared[-1].meta.get("parent")) is not parents[0][0]:
                            if token.level == close.level:
                                cleared[-1].meta["prior"] = token
                case markdown_it.token.Token(type="bullet_list_open" | "ordered_list_open"):
                    close, old = parents.pop()
                    if close.meta.get("end_code"):
                        token.map[1] = close.meta.get("end_code").map[0]
                    close.meta["open"] = token
                    if parents:
                        token.meta["parent"] = parents[-1][0]
                    if old and close.markup in self.list_items:
                        old = [x for x in old if x.markup in self.list_items]
                        old[-1].meta["open"].meta["first"] = old[0].meta["last"] = True
                    while cleared and cleared[-1].level <= token.level:
                        cleared.pop()
                    if parents and close is not parents[0][0]:
                        cleared.append(token)
                case markdown_it.token.Token(type="list_item_close"):
                    parents[-1][1].append(token)
                case markdown_it.token.Token(type="list_item_open"):
                    if parents:
                        if parents[-1][1][-1].meta.get("end_code"):
                            token.map[1] = parents[-1][0].meta.get("end_code").map[0] - 1
                        parents[-1][1][-1].meta["open"] = token
        if swaps:
            for swap in swaps:
                pos = len(tokens) - swap
                code = tokens.pop(pos)
                tokens.insert(pos + 2, code)
            return self.postlex(tokens, env)

        super().postlex(tokens, env)


@dataclass
class Defs(Python):
    def dl_open(self, token, env):
        parent = token.meta.get("parent")
        env["comment"] = bool(env.get("comment") or parent)
        if not parent:
            yield from self.noncode_block(env, token.map[0] - 1)
        prior = token.meta.get("prior")

        # if prior and prior.meta.get("open").meta.get("parent") is parent:
        #     # use the union operator to join separate dictionaries.
        #     # this allows for injected code in a definition list.
        #     yield "|"
        # else:
        if prior:
            yield " " * self.get_indent(env)

    def dl_close(self, token, env):
        env["comment"] = bool(token.meta["open"].meta.get("parent"))

    def dd_open(self, token, env):
        if token.meta.get("first_item") and not env.get("comment"):
            # start a list where a definition list item has multiple values
            yield from self.noncode_block(env, token.map[0] - 1, comment=True)
            yield "["
            env["continued"] = False
            env.update(comment=False, hanging=True)

    def dd_close(self, token, env):
        # close the definition list item(s)
        is_item = "last_item" in token.meta
        last, last_item = token.meta.get("last"), token.meta.get("last_item")

        if comment := env.get("comment"):
            if is_item:
                yield last_item and "]" or ","
            yield "})" if last else "" if last_item else ","
        yield from self.noncode_block(
            env, (open := token.meta.get("open")).map[1], whitespace=False, comment=comment
        )
        if not comment:
            if last_item:
                yield "]"
            yield "})" if last else "" if last_item else ","
        env["comment"] = bool(last and token.meta.get("parent"))
        env.update(hanging=False)

    def dt_open(self, token, env):
        if token.meta.get("first"):
            yield from self.noncode_block(env, token.map[0] - 1, comment=True)
            # define the left most part of the dictionary
            yield "({"
            env["continued"] = False
        env.update(comment=False, hanging=True)

    def dt_close(self, token, env):
        last = token.meta.get("last")
        yield from self.noncode_block(
            env,
            (open := token.meta.get("open")).map[1] + 1,
            whitespace=False,
            comment=env.get("comment"),
        )
        yield ":"
        if open.meta.get("parent"):
            env["comment"] = bool(token.meta.get("last"))
        env.update(hanging=False)

    def postlex(self, tokens, env):
        parents, cleared, swaps = [], [], []
        prior = None, None
        for i, token in enumerate(tokens[::-1], 1):
            if token.type == "code_block":
                if prior[1] is not None:
                    if prior[0].type == "dd_close" and prior[1].type == "dl_close":
                        prior[1].meta["end_code"] = prior[0].meta["end_code"] = token
                        swaps.append(i)
            prior = token, prior[0]
            match token:
                case markdown_it.token.Token(type="dl_close"):
                    parents.append((token, []))
                    if cleared:
                        if (parent := cleared[-1]) is not parents[0][0]:
                            if token.level == close.level:
                                cleared[-1].meta["prior"] = token
                case markdown_it.token.Token(type="dl_open"):
                    close, old = parents.pop()
                    if close.meta.get("end_code"):
                        token.map[1] = close.meta.get("end_code").map[0]
                    close.meta["open"] = token
                    if parents:
                        token.meta["parent"] = parents[-1][0]
                    dt, dd = None, []
                    for t in old:
                        match t:
                            case markdown_it.token.Token(type="dd_close"):
                                dd.append(t)
                            case markdown_it.token.Token(type="dt_close"):
                                dt = t
                                if len(dd) > 1:
                                    [d.meta.setdefault("last_item", None) for d in dd]
                                    dd[-1].meta["open"].meta.setdefault("first_item", True)
                                    dd[0].meta["last_item"] = True
                                dd.clear()
                    dt.meta["open"].meta["first"] = True
                    if old:
                        old[0].meta["last"] = True
                    while cleared and cleared[-1].level <= token.level:
                        cleared.pop()
                    if parents and close is not parents[0][0]:
                        cleared.append(token)
                case markdown_it.token.Token(type="dd_close" | "dt_close"):
                    parents[-1][1].append(token)
                case markdown_it.token.Token(type="dd_open" | "dt_open"):
                    if parents:
                        if parents[-1][1][-1].meta.get("end_code"):
                            token.map[1] = parents[-1][0].meta.get("end_code").map[0] - 1
                        parents[-1][1][-1].meta["open"] = token
        if swaps:
            for swap in swaps:
                pos = len(tokens) - swap
                code = tokens.pop(pos)
                tokens.insert(pos + 2, code)
            return self.postlex(tokens, env)
        super().postlex(tokens, env)


class Containers(Defs, Lists):
    def postlex(self, tokens, env):
        parents, cleared, swaps = [], [], []
        prior = None, None
        super().postlex(tokens, env)
        if swaps:
            for swap in swaps:
                pos = len(tokens) - swap
                code = tokens.pop(pos)
                tokens.insert(pos + 2, code)
            self.postlex(tokens, env)

        else:
            super().postlex(tokens, env)


def postlex(self, tokens, env):
    parents, cleared, swaps = [], [], []
    prior = None, None
    for i, token in enumerate(tokens[::-1], 1):
        if token.type == "code_block":
            if prior[1] is not None:
                if prior[0].type == "dd_close" and prior[1].type == "dl_close":
                    prior[1].meta["end_code"] = prior[0].meta["end_code"] = token
                    swaps.append(i)
        prior = token, prior[0]
        match token:
            case markdown_it.token.Token(type="dl_close"):
                parents.append((token, []))
                if cleared:
                    if (parent := cleared[-1]) is not parents[0][0]:
                        if token.level == close.level:
                            cleared[-1].meta["prior"] = token
            case markdown_it.token.Token(type="dl_open"):
                close, old = parents.pop()
                if close.meta.get("end_code"):
                    token.map[1] = close.meta.get("end_code").map[0]
                close.meta["open"] = token
                if parents:
                    token.meta["parent"] = parents[-1][0]
                dt, dd = None, []
                for t in old:
                    match t:
                        case markdown_it.token.Token(type="dd_close"):
                            dd.append(t)
                        case markdown_it.token.Token(type="dt_close"):
                            dt = t
                            if len(dd) > 1:
                                [d.meta.setdefault("last_item", None) for d in dd]
                                dd[-1].meta["open"].meta.setdefault("first_item", True)
                                dd[0].meta["last_item"] = True
                            dd.clear()
                dt.meta["open"].meta["first"] = True
                if old:
                    old[0].meta["last"] = True
                while cleared and cleared[-1].level <= token.level:
                    cleared.pop()
                if parents and close is not parents[0][0]:
                    cleared.append(token)
            case markdown_it.token.Token(type="dd_close" | "dt_close"):
                parents[-1][1].append(token)
            case markdown_it.token.Token(type="dd_open" | "dt_open"):
                if parents:
                    if parents[-1][1][-1].meta.get("end_code"):
                        token.map[1] = parents[-1][0].meta.get("end_code").map[0] - 1
                    parents[-1][1][-1].meta["open"] = token
    if swaps:
        for swap in swaps:
            pos = len(tokens) - swap
            code = tokens.pop(pos)
            tokens.insert(pos + 2, code)
        return self.postlex(tokens, env)
    super().postlex(tokens, env)
