SUPPORT = 'rules = {}\n\nclass Stream:\n\n    def __init__(self, items):\n        self.items = items\n        self.index = 0\n        self.latest_error = None\n        self.scope = None\n\n    def operator_or(self, matchers):\n        for matcher in matchers:\n            backtrack_index = self.index\n            try:\n                return matcher.run(self)\n            except MatchError:\n                self.index = backtrack_index\n        self.error("no or match")\n\n    def operator_and(self, matchers):\n        result = self.action()\n        for matcher in matchers:\n            result = matcher.run(self)\n        return result\n\n    def operator_star(self, matcher):\n        results = []\n        while True:\n            backtrack_index = self.index\n            try:\n                results.append(matcher.run(self))\n            except MatchError:\n                self.index = backtrack_index\n                return self.action(lambda self: [x.eval(self.runtime) for x in results])\n\n    def operator_not(self, matcher):\n        backtrack_index = self.index\n        try:\n            matcher.run(self)\n        except MatchError:\n            return self.action()\n        finally:\n            self.index = backtrack_index\n        self.error("not matched")\n\n    def action(self, fn=lambda self: None):\n        return SemanticAction(self.scope, fn)\n\n    def with_scope(self, matcher):\n        current_scope = self.scope\n        self.scope = {}\n        try:\n            return matcher.run(self)\n        finally:\n            self.scope = current_scope\n\n    def bind(self, name, semantic_action):\n        self.scope[name] = semantic_action\n        return semantic_action\n\n    def match_list(self, matcher):\n        if self.index < len(self.items):\n            items, index = self.items, self.index\n            try:\n                self.items = self.items[self.index]\n                self.index = 0\n                result = matcher.run(self)\n                index += 1\n            finally:\n                self.items, self.index = items, index\n            return result\n        self.error("no list found")\n\n    def match_call_rule(self, namespace):\n        name = namespace + "." + self.items[self.index]\n        if name in rules:\n            rule = rules[name]\n            self.index += 1\n            return rule.run(self)\n        else:\n            self.error("unknown rule")\n\n    def match(self, fn, description):\n        if self.index < len(self.items):\n            item = self.items[self.index]\n            if fn(item):\n                self.index += 1\n                return self.action(lambda self: item)\n        self.error(f"expected {description}")\n\n    def error(self, name):\n        if not self.latest_error or self.index > self.latest_error[2]:\n            self.latest_error = (name, self.items, self.index)\n        raise MatchError(*self.latest_error)\n\nclass MatchError(Exception):\n\n    def __init__(self, name, items, index):\n        Exception.__init__(self, name)\n        self.items = items\n        self.index = index\n\nclass SemanticAction:\n\n    def __init__(self, scope, fn):\n        self.scope = scope\n        self.fn = fn\n\n    def eval(self, runtime):\n        self.runtime = runtime\n        return self.fn(self)\n\n    def bind(self, name, value, continuation):\n        self.runtime = self.runtime.bind(name, value)\n        return continuation()\n\n    def lookup(self, name):\n        if name in self.scope:\n            return self.scope[name].eval(self.runtime)\n        else:\n            return self.runtime.lookup(name)\n\nclass Runtime:\n\n    def __init__(self, extra={"len": len, "repr": repr}):\n        self.vars = extra\n\n    def bind(self, name, value):\n        return Runtime(dict(self.vars, **{name: value}))\n\n    def lookup(self, name):\n        if name in self.vars:\n            return self.vars[name]\n        else:\n            return getattr(self, name)\n\n    def append(self, list, thing):\n        list.append(thing)\n\n    def join(self, items, delimiter=""):\n        return delimiter.join(\n            self.join(item, delimiter) if isinstance(item, list) else str(item)\n            for item in items\n        )\n\n    def indent(self, text, prefix="    "):\n        return "".join(prefix+line for line in text.splitlines(True))\n\n    def splice(self, depth, item):\n        if depth == 0:\n            return [item]\n        else:\n            return self.concat([self.splice(depth-1, subitem) for subitem in item])\n\n    def concat(self, lists):\n        return [x for xs in lists for x in xs]\n\ndef compile_chain(grammars, source):\n    import os\n    import sys\n    import pprint\n    runtime = Runtime()\n    for rule in grammars:\n        try:\n            source = rules[rule].run(Stream(source)).eval(runtime)\n        except MatchError as e:\n            marker = "<ERROR POSITION>"\n            if os.isatty(sys.stderr.fileno()):\n                marker = f"\\033[0;31m{marker}\\033[0m"\n            if isinstance(e.items, str):\n                stream_string = e.items[:e.index] + marker + e.items[e.index:]\n            else:\n                stream_string = pprint.pformat(e.items)\n            sys.exit("ERROR: {}\\nPOSITION: {}\\nSTREAM:\\n{}".format(\n                str(e),\n                e.index,\n                runtime.indent(stream_string)\n            ))\n    return source\n'
rules = {}

class Stream:

    def __init__(self, items):
        self.items = items
        self.index = 0
        self.latest_error = None
        self.scope = None

    def operator_or(self, matchers):
        for matcher in matchers:
            backtrack_index = self.index
            try:
                return matcher.run(self)
            except MatchError:
                self.index = backtrack_index
        self.error("no or match")

    def operator_and(self, matchers):
        result = self.action()
        for matcher in matchers:
            result = matcher.run(self)
        return result

    def operator_star(self, matcher):
        results = []
        while True:
            backtrack_index = self.index
            try:
                results.append(matcher.run(self))
            except MatchError:
                self.index = backtrack_index
                return self.action(lambda self: [x.eval(self.runtime) for x in results])

    def operator_not(self, matcher):
        backtrack_index = self.index
        try:
            matcher.run(self)
        except MatchError:
            return self.action()
        finally:
            self.index = backtrack_index
        self.error("not matched")

    def action(self, fn=lambda self: None):
        return SemanticAction(self.scope, fn)

    def with_scope(self, matcher):
        current_scope = self.scope
        self.scope = {}
        try:
            return matcher.run(self)
        finally:
            self.scope = current_scope

    def bind(self, name, semantic_action):
        self.scope[name] = semantic_action
        return semantic_action

    def match_list(self, matcher):
        if self.index < len(self.items):
            items, index = self.items, self.index
            try:
                self.items = self.items[self.index]
                self.index = 0
                result = matcher.run(self)
                index += 1
            finally:
                self.items, self.index = items, index
            return result
        self.error("no list found")

    def match_call_rule(self, namespace):
        name = namespace + "." + self.items[self.index]
        if name in rules:
            rule = rules[name]
            self.index += 1
            return rule.run(self)
        else:
            self.error("unknown rule")

    def match(self, fn, description):
        if self.index < len(self.items):
            item = self.items[self.index]
            if fn(item):
                self.index += 1
                return self.action(lambda self: item)
        self.error(f"expected {description}")

    def error(self, name):
        if not self.latest_error or self.index > self.latest_error[2]:
            self.latest_error = (name, self.items, self.index)
        raise MatchError(*self.latest_error)

class MatchError(Exception):

    def __init__(self, name, items, index):
        Exception.__init__(self, name)
        self.items = items
        self.index = index

class SemanticAction:

    def __init__(self, scope, fn):
        self.scope = scope
        self.fn = fn

    def eval(self, runtime):
        self.runtime = runtime
        return self.fn(self)

    def bind(self, name, value, continuation):
        self.runtime = self.runtime.bind(name, value)
        return continuation()

    def lookup(self, name):
        if name in self.scope:
            return self.scope[name].eval(self.runtime)
        else:
            return self.runtime.lookup(name)

class Runtime:

    def __init__(self, extra={"len": len, "repr": repr}):
        self.vars = extra

    def bind(self, name, value):
        return Runtime(dict(self.vars, **{name: value}))

    def lookup(self, name):
        if name in self.vars:
            return self.vars[name]
        else:
            return getattr(self, name)

    def append(self, list, thing):
        list.append(thing)

    def join(self, items, delimiter=""):
        return delimiter.join(
            self.join(item, delimiter) if isinstance(item, list) else str(item)
            for item in items
        )

    def indent(self, text, prefix="    "):
        return "".join(prefix+line for line in text.splitlines(True))

    def splice(self, depth, item):
        if depth == 0:
            return [item]
        else:
            return self.concat([self.splice(depth-1, subitem) for subitem in item])

    def concat(self, lists):
        return [x for xs in lists for x in xs]

def compile_chain(grammars, source):
    import os
    import sys
    import pprint
    runtime = Runtime()
    for rule in grammars:
        try:
            source = rules[rule].run(Stream(source)).eval(runtime)
        except MatchError as e:
            marker = "<ERROR POSITION>"
            if os.isatty(sys.stderr.fileno()):
                marker = f"\033[0;31m{marker}\033[0m"
            if isinstance(e.items, str):
                stream_string = e.items[:e.index] + marker + e.items[e.index:]
            else:
                stream_string = pprint.pformat(e.items)
            sys.exit("ERROR: {}\nPOSITION: {}\nSTREAM:\n{}".format(
                str(e),
                e.index,
                runtime.indent(stream_string)
            ))
    return source
class Matcher_Parser_0:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_1:
    def run(self, stream):
        return rules['Parser.namespace'].run(stream)
class Matcher_Parser_2:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_0(),
            Matcher_Parser_1()
        ])
class Matcher_Parser_3:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_2())
class Matcher_Parser_4:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_3()
        ])
class Matcher_Parser_5:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_4())
class Matcher_Parser_6:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_5().run(stream))
class Matcher_Parser_7:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_8:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_Parser_9:
    def run(self, stream):
        return stream.operator_not(Matcher_Parser_8())
class Matcher_Parser_10:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('xs'))
class Matcher_Parser_11:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_6(),
            Matcher_Parser_7(),
            Matcher_Parser_9(),
            Matcher_Parser_10()
        ])
class Matcher_Parser_12:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_11())
class Matcher_Parser_13:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_12()
        ])
class Matcher_Parser_14:
    def run(self, stream):
        return rules['Parser.name'].run(stream)
class Matcher_Parser_15:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_14().run(stream))
class Matcher_Parser_16:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_17:
    def run(self, stream):
        return stream.match(lambda item: item == '{', "'{'")
class Matcher_Parser_18:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_17()
        ])
class Matcher_Parser_19:
    def run(self, stream):
        return rules['Parser.rule'].run(stream)
class Matcher_Parser_20:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_19())
class Matcher_Parser_21:
    def run(self, stream):
        return stream.bind('ys', Matcher_Parser_20().run(stream))
class Matcher_Parser_22:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_23:
    def run(self, stream):
        return stream.match(lambda item: item == '}', "'}'")
class Matcher_Parser_24:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_23()
        ])
class Matcher_Parser_25:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Namespace'),
            self.lookup('splice')(0, self.lookup('x')),
            self.lookup('splice')(1, self.lookup('ys'))
        ]))
class Matcher_Parser_26:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_15(),
            Matcher_Parser_16(),
            Matcher_Parser_18(),
            Matcher_Parser_21(),
            Matcher_Parser_22(),
            Matcher_Parser_24(),
            Matcher_Parser_25()
        ])
class Matcher_Parser_27:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_26())
class Matcher_Parser_28:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_27()
        ])
class Matcher_Parser_29:
    def run(self, stream):
        return rules['Parser.name'].run(stream)
class Matcher_Parser_30:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_29().run(stream))
class Matcher_Parser_31:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_32:
    def run(self, stream):
        return stream.match(lambda item: item == '=', "'='")
class Matcher_Parser_33:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_32()
        ])
class Matcher_Parser_34:
    def run(self, stream):
        return rules['Parser.choice'].run(stream)
class Matcher_Parser_35:
    def run(self, stream):
        return stream.bind('y', Matcher_Parser_34().run(stream))
class Matcher_Parser_36:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Rule'),
            self.lookup('splice')(0, self.lookup('x')),
            self.lookup('splice')(0, self.lookup('y'))
        ]))
class Matcher_Parser_37:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_30(),
            Matcher_Parser_31(),
            Matcher_Parser_33(),
            Matcher_Parser_35(),
            Matcher_Parser_36()
        ])
class Matcher_Parser_38:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_37())
class Matcher_Parser_39:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_38()
        ])
class Matcher_Parser_40:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_41:
    def run(self, stream):
        return stream.match(lambda item: item == '|', "'|'")
class Matcher_Parser_42:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_41()
        ])
class Matcher_Parser_43:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_40(),
            Matcher_Parser_42()
        ])
class Matcher_Parser_44:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_43())
class Matcher_Parser_45:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_44()
        ])
class Matcher_Parser_46:
    def run(self, stream):
        return stream.operator_and([
        
        ])
class Matcher_Parser_47:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_45(),
            Matcher_Parser_46()
        ])
class Matcher_Parser_48:
    def run(self, stream):
        return rules['Parser.sequence'].run(stream)
class Matcher_Parser_49:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_48().run(stream))
class Matcher_Parser_50:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_51:
    def run(self, stream):
        return stream.match(lambda item: item == '|', "'|'")
class Matcher_Parser_52:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_51()
        ])
class Matcher_Parser_53:
    def run(self, stream):
        return rules['Parser.sequence'].run(stream)
class Matcher_Parser_54:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_50(),
            Matcher_Parser_52(),
            Matcher_Parser_53()
        ])
class Matcher_Parser_55:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_54())
class Matcher_Parser_56:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_55()
        ])
class Matcher_Parser_57:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_56())
class Matcher_Parser_58:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_57().run(stream))
class Matcher_Parser_59:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Or'),
            self.lookup('splice')(0, self.lookup('x')),
            self.lookup('splice')(1, self.lookup('xs'))
        ]))
class Matcher_Parser_60:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_47(),
            Matcher_Parser_49(),
            Matcher_Parser_58(),
            Matcher_Parser_59()
        ])
class Matcher_Parser_61:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_60())
class Matcher_Parser_62:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_61()
        ])
class Matcher_Parser_63:
    def run(self, stream):
        return rules['Parser.expr'].run(stream)
class Matcher_Parser_64:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_63())
class Matcher_Parser_65:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_64().run(stream))
class Matcher_Parser_66:
    def run(self, stream):
        return rules['Parser.maybeAction'].run(stream)
class Matcher_Parser_67:
    def run(self, stream):
        return stream.bind('ys', Matcher_Parser_66().run(stream))
class Matcher_Parser_68:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Scope'),
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'And'),
                self.lookup('splice')(1, self.lookup('xs')),
                self.lookup('splice')(1, self.lookup('ys'))
            ]))
        ]))
class Matcher_Parser_69:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_65(),
            Matcher_Parser_67(),
            Matcher_Parser_68()
        ])
class Matcher_Parser_70:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_69())
class Matcher_Parser_71:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_70()
        ])
class Matcher_Parser_72:
    def run(self, stream):
        return rules['Parser.expr1'].run(stream)
class Matcher_Parser_73:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_72().run(stream))
class Matcher_Parser_74:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_75:
    def run(self, stream):
        return stream.match(lambda item: item == ':', "':'")
class Matcher_Parser_76:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_75()
        ])
class Matcher_Parser_77:
    def run(self, stream):
        return rules['Parser.name'].run(stream)
class Matcher_Parser_78:
    def run(self, stream):
        return stream.bind('y', Matcher_Parser_77().run(stream))
class Matcher_Parser_79:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Bind'),
            self.lookup('splice')(0, self.lookup('y')),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_80:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_73(),
            Matcher_Parser_74(),
            Matcher_Parser_76(),
            Matcher_Parser_78(),
            Matcher_Parser_79()
        ])
class Matcher_Parser_81:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_80())
class Matcher_Parser_82:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_83:
    def run(self, stream):
        return stream.match(lambda item: item == '[', "'['")
class Matcher_Parser_84:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_83()
        ])
class Matcher_Parser_85:
    def run(self, stream):
        return rules['Parser.expr'].run(stream)
class Matcher_Parser_86:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_85())
class Matcher_Parser_87:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_86().run(stream))
class Matcher_Parser_88:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_89:
    def run(self, stream):
        return stream.match(lambda item: item == ']', "']'")
class Matcher_Parser_90:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_89()
        ])
class Matcher_Parser_91:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'MatchList'),
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'And'),
                self.lookup('splice')(1, self.lookup('xs'))
            ]))
        ]))
class Matcher_Parser_92:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_82(),
            Matcher_Parser_84(),
            Matcher_Parser_87(),
            Matcher_Parser_88(),
            Matcher_Parser_90(),
            Matcher_Parser_91()
        ])
class Matcher_Parser_93:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_92())
class Matcher_Parser_94:
    def run(self, stream):
        return rules['Parser.expr1'].run(stream)
class Matcher_Parser_95:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_94()
        ])
class Matcher_Parser_96:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_95())
class Matcher_Parser_97:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_81(),
            Matcher_Parser_93(),
            Matcher_Parser_96()
        ])
class Matcher_Parser_98:
    def run(self, stream):
        return rules['Parser.expr2'].run(stream)
class Matcher_Parser_99:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_98().run(stream))
class Matcher_Parser_100:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_101:
    def run(self, stream):
        return stream.match(lambda item: item == '*', "'*'")
class Matcher_Parser_102:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_101()
        ])
class Matcher_Parser_103:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Star'),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_104:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_99(),
            Matcher_Parser_100(),
            Matcher_Parser_102(),
            Matcher_Parser_103()
        ])
class Matcher_Parser_105:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_104())
class Matcher_Parser_106:
    def run(self, stream):
        return rules['Parser.expr2'].run(stream)
class Matcher_Parser_107:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_106().run(stream))
class Matcher_Parser_108:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_109:
    def run(self, stream):
        return stream.match(lambda item: item == '?', "'?'")
class Matcher_Parser_110:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_109()
        ])
class Matcher_Parser_111:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Or'),
            self.lookup('splice')(0, self.lookup('x')),
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'And')
            ]))
        ]))
class Matcher_Parser_112:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_107(),
            Matcher_Parser_108(),
            Matcher_Parser_110(),
            Matcher_Parser_111()
        ])
class Matcher_Parser_113:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_112())
class Matcher_Parser_114:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_115:
    def run(self, stream):
        return stream.match(lambda item: item == '!', "'!'")
class Matcher_Parser_116:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_115()
        ])
class Matcher_Parser_117:
    def run(self, stream):
        return rules['Parser.expr2'].run(stream)
class Matcher_Parser_118:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_117().run(stream))
class Matcher_Parser_119:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Not'),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_120:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_114(),
            Matcher_Parser_116(),
            Matcher_Parser_118(),
            Matcher_Parser_119()
        ])
class Matcher_Parser_121:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_120())
class Matcher_Parser_122:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_123:
    def run(self, stream):
        return stream.match(lambda item: item == '%', "'%'")
class Matcher_Parser_124:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_123()
        ])
class Matcher_Parser_125:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'MatchCallRule')
        ]))
class Matcher_Parser_126:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_122(),
            Matcher_Parser_124(),
            Matcher_Parser_125()
        ])
class Matcher_Parser_127:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_126())
class Matcher_Parser_128:
    def run(self, stream):
        return rules['Parser.expr2'].run(stream)
class Matcher_Parser_129:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_128()
        ])
class Matcher_Parser_130:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_129())
class Matcher_Parser_131:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_105(),
            Matcher_Parser_113(),
            Matcher_Parser_121(),
            Matcher_Parser_127(),
            Matcher_Parser_130()
        ])
class Matcher_Parser_132:
    def run(self, stream):
        return rules['Parser.name'].run(stream)
class Matcher_Parser_133:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_132().run(stream))
class Matcher_Parser_134:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_135:
    def run(self, stream):
        return stream.match(lambda item: item == '=', "'='")
class Matcher_Parser_136:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_135()
        ])
class Matcher_Parser_137:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_134(),
            Matcher_Parser_136()
        ])
class Matcher_Parser_138:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_137())
class Matcher_Parser_139:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_138()
        ])
class Matcher_Parser_140:
    def run(self, stream):
        return stream.operator_not(Matcher_Parser_139())
class Matcher_Parser_141:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'MatchRule'),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_142:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_133(),
            Matcher_Parser_140(),
            Matcher_Parser_141()
        ])
class Matcher_Parser_143:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_142())
class Matcher_Parser_144:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_145:
    def run(self, stream):
        return rules['Parser.char'].run(stream)
class Matcher_Parser_146:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_145().run(stream))
class Matcher_Parser_147:
    def run(self, stream):
        return stream.match(lambda item: item == '-', "'-'")
class Matcher_Parser_148:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_147()
        ])
class Matcher_Parser_149:
    def run(self, stream):
        return rules['Parser.char'].run(stream)
class Matcher_Parser_150:
    def run(self, stream):
        return stream.bind('y', Matcher_Parser_149().run(stream))
class Matcher_Parser_151:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'MatchObject'),
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'Range'),
                self.lookup('splice')(0, self.lookup('x')),
                self.lookup('splice')(0, self.lookup('y'))
            ]))
        ]))
class Matcher_Parser_152:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_144(),
            Matcher_Parser_146(),
            Matcher_Parser_148(),
            Matcher_Parser_150(),
            Matcher_Parser_151()
        ])
class Matcher_Parser_153:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_152())
class Matcher_Parser_154:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_155:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_156:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_155()
        ])
class Matcher_Parser_157:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_158:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_157()
        ])
class Matcher_Parser_159:
    def run(self, stream):
        return stream.operator_not(Matcher_Parser_158())
class Matcher_Parser_160:
    def run(self, stream):
        return rules['Parser.matchChar'].run(stream)
class Matcher_Parser_161:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_159(),
            Matcher_Parser_160()
        ])
class Matcher_Parser_162:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_161())
class Matcher_Parser_163:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_162()
        ])
class Matcher_Parser_164:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_163())
class Matcher_Parser_165:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_164().run(stream))
class Matcher_Parser_166:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_167:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_166()
        ])
class Matcher_Parser_168:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'And'),
            self.lookup('splice')(1, self.lookup('xs'))
        ]))
class Matcher_Parser_169:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_154(),
            Matcher_Parser_156(),
            Matcher_Parser_165(),
            Matcher_Parser_167(),
            Matcher_Parser_168()
        ])
class Matcher_Parser_170:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_169())
class Matcher_Parser_171:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_172:
    def run(self, stream):
        return stream.match(lambda item: item == '.', "'.'")
class Matcher_Parser_173:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_172()
        ])
class Matcher_Parser_174:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'MatchObject'),
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'Any')
            ]))
        ]))
class Matcher_Parser_175:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_171(),
            Matcher_Parser_173(),
            Matcher_Parser_174()
        ])
class Matcher_Parser_176:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_175())
class Matcher_Parser_177:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_178:
    def run(self, stream):
        return stream.match(lambda item: item == '(', "'('")
class Matcher_Parser_179:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_178()
        ])
class Matcher_Parser_180:
    def run(self, stream):
        return rules['Parser.choice'].run(stream)
class Matcher_Parser_181:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_180().run(stream))
class Matcher_Parser_182:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_183:
    def run(self, stream):
        return stream.match(lambda item: item == ')', "')'")
class Matcher_Parser_184:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_183()
        ])
class Matcher_Parser_185:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('x'))
class Matcher_Parser_186:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_177(),
            Matcher_Parser_179(),
            Matcher_Parser_181(),
            Matcher_Parser_182(),
            Matcher_Parser_184(),
            Matcher_Parser_185()
        ])
class Matcher_Parser_187:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_186())
class Matcher_Parser_188:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_143(),
            Matcher_Parser_153(),
            Matcher_Parser_170(),
            Matcher_Parser_176(),
            Matcher_Parser_187()
        ])
class Matcher_Parser_189:
    def run(self, stream):
        return rules['Parser.innerChar'].run(stream)
class Matcher_Parser_190:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_189().run(stream))
class Matcher_Parser_191:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'MatchObject'),
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'Eq'),
                self.lookup('splice')(0, self.lookup('x'))
            ]))
        ]))
class Matcher_Parser_192:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_190(),
            Matcher_Parser_191()
        ])
class Matcher_Parser_193:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_192())
class Matcher_Parser_194:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_193()
        ])
class Matcher_Parser_195:
    def run(self, stream):
        return rules['Parser.actionExpr'].run(stream)
class Matcher_Parser_196:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_195().run(stream))
class Matcher_Parser_197:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, self.lookup('concat')([
                self.lookup('splice')(0, 'Action'),
                self.lookup('splice')(0, self.lookup('x'))
            ]))
        ]))
class Matcher_Parser_198:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_196(),
            Matcher_Parser_197()
        ])
class Matcher_Parser_199:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_198())
class Matcher_Parser_200:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
        
        ]))
class Matcher_Parser_201:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_200()
        ])
class Matcher_Parser_202:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_201())
class Matcher_Parser_203:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_199(),
            Matcher_Parser_202()
        ])
class Matcher_Parser_204:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_205:
    def run(self, stream):
        return stream.match(lambda item: item == '-', "'-'")
class Matcher_Parser_206:
    def run(self, stream):
        return stream.match(lambda item: item == '>', "'>'")
class Matcher_Parser_207:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_205(),
            Matcher_Parser_206()
        ])
class Matcher_Parser_208:
    def run(self, stream):
        return rules['Parser.hostExpr'].run(stream)
class Matcher_Parser_209:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_208().run(stream))
class Matcher_Parser_210:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_211:
    def run(self, stream):
        return stream.match(lambda item: item == ':', "':'")
class Matcher_Parser_212:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_211()
        ])
class Matcher_Parser_213:
    def run(self, stream):
        return rules['Parser.name'].run(stream)
class Matcher_Parser_214:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_210(),
            Matcher_Parser_212(),
            Matcher_Parser_213()
        ])
class Matcher_Parser_215:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_214())
class Matcher_Parser_216:
    def run(self, stream):
        return stream.action(lambda self: '')
class Matcher_Parser_217:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_216()
        ])
class Matcher_Parser_218:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_217())
class Matcher_Parser_219:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_215(),
            Matcher_Parser_218()
        ])
class Matcher_Parser_220:
    def run(self, stream):
        return stream.bind('y', Matcher_Parser_219().run(stream))
class Matcher_Parser_221:
    def run(self, stream):
        return rules['Parser.actionExpr'].run(stream)
class Matcher_Parser_222:
    def run(self, stream):
        return stream.bind('z', Matcher_Parser_221().run(stream))
class Matcher_Parser_223:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Set'),
            self.lookup('splice')(0, self.lookup('y')),
            self.lookup('splice')(0, self.lookup('x')),
            self.lookup('splice')(0, self.lookup('z'))
        ]))
class Matcher_Parser_224:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_204(),
            Matcher_Parser_207(),
            Matcher_Parser_209(),
            Matcher_Parser_220(),
            Matcher_Parser_222(),
            Matcher_Parser_223()
        ])
class Matcher_Parser_225:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_224())
class Matcher_Parser_226:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_227:
    def run(self, stream):
        return stream.match(lambda item: item == '-', "'-'")
class Matcher_Parser_228:
    def run(self, stream):
        return stream.match(lambda item: item == '>', "'>'")
class Matcher_Parser_229:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_227(),
            Matcher_Parser_228()
        ])
class Matcher_Parser_230:
    def run(self, stream):
        return rules['Parser.hostExpr'].run(stream)
class Matcher_Parser_231:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_226(),
            Matcher_Parser_229(),
            Matcher_Parser_230()
        ])
class Matcher_Parser_232:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_231())
class Matcher_Parser_233:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_225(),
            Matcher_Parser_232()
        ])
class Matcher_Parser_234:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_235:
    def run(self, stream):
        return rules['Parser.string'].run(stream)
class Matcher_Parser_236:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_235().run(stream))
class Matcher_Parser_237:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'String'),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_238:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_234(),
            Matcher_Parser_236(),
            Matcher_Parser_237()
        ])
class Matcher_Parser_239:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_238())
class Matcher_Parser_240:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_241:
    def run(self, stream):
        return stream.match(lambda item: item == '[', "'['")
class Matcher_Parser_242:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_241()
        ])
class Matcher_Parser_243:
    def run(self, stream):
        return rules['Parser.hostListItem'].run(stream)
class Matcher_Parser_244:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_243())
class Matcher_Parser_245:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_244().run(stream))
class Matcher_Parser_246:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_247:
    def run(self, stream):
        return stream.match(lambda item: item == ']', "']'")
class Matcher_Parser_248:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_247()
        ])
class Matcher_Parser_249:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'List'),
            self.lookup('splice')(1, self.lookup('xs'))
        ]))
class Matcher_Parser_250:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_240(),
            Matcher_Parser_242(),
            Matcher_Parser_245(),
            Matcher_Parser_246(),
            Matcher_Parser_248(),
            Matcher_Parser_249()
        ])
class Matcher_Parser_251:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_250())
class Matcher_Parser_252:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_253:
    def run(self, stream):
        return stream.match(lambda item: item == '{', "'{'")
class Matcher_Parser_254:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_253()
        ])
class Matcher_Parser_255:
    def run(self, stream):
        return rules['Parser.hostExpr'].run(stream)
class Matcher_Parser_256:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_255())
class Matcher_Parser_257:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_256().run(stream))
class Matcher_Parser_258:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_259:
    def run(self, stream):
        return stream.match(lambda item: item == '}', "'}'")
class Matcher_Parser_260:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_259()
        ])
class Matcher_Parser_261:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Format'),
            self.lookup('splice')(1, self.lookup('xs'))
        ]))
class Matcher_Parser_262:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_252(),
            Matcher_Parser_254(),
            Matcher_Parser_257(),
            Matcher_Parser_258(),
            Matcher_Parser_260(),
            Matcher_Parser_261()
        ])
class Matcher_Parser_263:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_262())
class Matcher_Parser_264:
    def run(self, stream):
        return rules['Parser.var'].run(stream)
class Matcher_Parser_265:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_264().run(stream))
class Matcher_Parser_266:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_267:
    def run(self, stream):
        return stream.match(lambda item: item == '(', "'('")
class Matcher_Parser_268:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_267()
        ])
class Matcher_Parser_269:
    def run(self, stream):
        return rules['Parser.hostExpr'].run(stream)
class Matcher_Parser_270:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_269())
class Matcher_Parser_271:
    def run(self, stream):
        return stream.bind('ys', Matcher_Parser_270().run(stream))
class Matcher_Parser_272:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_273:
    def run(self, stream):
        return stream.match(lambda item: item == ')', "')'")
class Matcher_Parser_274:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_273()
        ])
class Matcher_Parser_275:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Call'),
            self.lookup('splice')(0, self.lookup('x')),
            self.lookup('splice')(1, self.lookup('ys'))
        ]))
class Matcher_Parser_276:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_265(),
            Matcher_Parser_266(),
            Matcher_Parser_268(),
            Matcher_Parser_271(),
            Matcher_Parser_272(),
            Matcher_Parser_274(),
            Matcher_Parser_275()
        ])
class Matcher_Parser_277:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_276())
class Matcher_Parser_278:
    def run(self, stream):
        return rules['Parser.var'].run(stream)
class Matcher_Parser_279:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_278()
        ])
class Matcher_Parser_280:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_279())
class Matcher_Parser_281:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_239(),
            Matcher_Parser_251(),
            Matcher_Parser_263(),
            Matcher_Parser_277(),
            Matcher_Parser_280()
        ])
class Matcher_Parser_282:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_283:
    def run(self, stream):
        return stream.match(lambda item: item == '~', "'~'")
class Matcher_Parser_284:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_283()
        ])
class Matcher_Parser_285:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_284())
class Matcher_Parser_286:
    def run(self, stream):
        return stream.bind('ys', Matcher_Parser_285().run(stream))
class Matcher_Parser_287:
    def run(self, stream):
        return rules['Parser.hostExpr'].run(stream)
class Matcher_Parser_288:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_287().run(stream))
class Matcher_Parser_289:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'ListItem'),
            self.lookup('splice')(0, self.lookup('len')(
                self.lookup('ys')
            )),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_290:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_282(),
            Matcher_Parser_286(),
            Matcher_Parser_288(),
            Matcher_Parser_289()
        ])
class Matcher_Parser_291:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_290())
class Matcher_Parser_292:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_291()
        ])
class Matcher_Parser_293:
    def run(self, stream):
        return rules['Parser.name'].run(stream)
class Matcher_Parser_294:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_293().run(stream))
class Matcher_Parser_295:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_296:
    def run(self, stream):
        return stream.match(lambda item: item == '=', "'='")
class Matcher_Parser_297:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_296()
        ])
class Matcher_Parser_298:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_295(),
            Matcher_Parser_297()
        ])
class Matcher_Parser_299:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_298())
class Matcher_Parser_300:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_299()
        ])
class Matcher_Parser_301:
    def run(self, stream):
        return stream.operator_not(Matcher_Parser_300())
class Matcher_Parser_302:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('concat')([
            self.lookup('splice')(0, 'Lookup'),
            self.lookup('splice')(0, self.lookup('x'))
        ]))
class Matcher_Parser_303:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_294(),
            Matcher_Parser_301(),
            Matcher_Parser_302()
        ])
class Matcher_Parser_304:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_303())
class Matcher_Parser_305:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_304()
        ])
class Matcher_Parser_306:
    def run(self, stream):
        return stream.match(lambda item: item == '"', '\'"\'')
class Matcher_Parser_307:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_306()
        ])
class Matcher_Parser_308:
    def run(self, stream):
        return stream.match(lambda item: item == '"', '\'"\'')
class Matcher_Parser_309:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_308()
        ])
class Matcher_Parser_310:
    def run(self, stream):
        return stream.operator_not(Matcher_Parser_309())
class Matcher_Parser_311:
    def run(self, stream):
        return rules['Parser.innerChar'].run(stream)
class Matcher_Parser_312:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_310(),
            Matcher_Parser_311()
        ])
class Matcher_Parser_313:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_312())
class Matcher_Parser_314:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_313()
        ])
class Matcher_Parser_315:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_314())
class Matcher_Parser_316:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_315().run(stream))
class Matcher_Parser_317:
    def run(self, stream):
        return stream.match(lambda item: item == '"', '\'"\'')
class Matcher_Parser_318:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_317()
        ])
class Matcher_Parser_319:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            self.lookup('xs')
        ]))
class Matcher_Parser_320:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_307(),
            Matcher_Parser_316(),
            Matcher_Parser_318(),
            Matcher_Parser_319()
        ])
class Matcher_Parser_321:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_320())
class Matcher_Parser_322:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_321()
        ])
class Matcher_Parser_323:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_324:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_323()
        ])
class Matcher_Parser_325:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_326:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_325()
        ])
class Matcher_Parser_327:
    def run(self, stream):
        return stream.operator_not(Matcher_Parser_326())
class Matcher_Parser_328:
    def run(self, stream):
        return rules['Parser.innerChar'].run(stream)
class Matcher_Parser_329:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_328().run(stream))
class Matcher_Parser_330:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_331:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_330()
        ])
class Matcher_Parser_332:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('x'))
class Matcher_Parser_333:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_324(),
            Matcher_Parser_327(),
            Matcher_Parser_329(),
            Matcher_Parser_331(),
            Matcher_Parser_332()
        ])
class Matcher_Parser_334:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_333())
class Matcher_Parser_335:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_334()
        ])
class Matcher_Parser_336:
    def run(self, stream):
        return stream.match(lambda item: item == '\\', "'\\\\'")
class Matcher_Parser_337:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_336()
        ])
class Matcher_Parser_338:
    def run(self, stream):
        return rules['Parser.escape'].run(stream)
class Matcher_Parser_339:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_337(),
            Matcher_Parser_338()
        ])
class Matcher_Parser_340:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_339())
class Matcher_Parser_341:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_Parser_342:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_341()
        ])
class Matcher_Parser_343:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_342())
class Matcher_Parser_344:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_340(),
            Matcher_Parser_343()
        ])
class Matcher_Parser_345:
    def run(self, stream):
        return stream.match(lambda item: item == '\\', "'\\\\'")
class Matcher_Parser_346:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_345()
        ])
class Matcher_Parser_347:
    def run(self, stream):
        return stream.action(lambda self: '\\')
class Matcher_Parser_348:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_346(),
            Matcher_Parser_347()
        ])
class Matcher_Parser_349:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_348())
class Matcher_Parser_350:
    def run(self, stream):
        return stream.match(lambda item: item == "'", '"\'"')
class Matcher_Parser_351:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_350()
        ])
class Matcher_Parser_352:
    def run(self, stream):
        return stream.action(lambda self: "'")
class Matcher_Parser_353:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_351(),
            Matcher_Parser_352()
        ])
class Matcher_Parser_354:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_353())
class Matcher_Parser_355:
    def run(self, stream):
        return stream.match(lambda item: item == '"', '\'"\'')
class Matcher_Parser_356:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_355()
        ])
class Matcher_Parser_357:
    def run(self, stream):
        return stream.action(lambda self: '"')
class Matcher_Parser_358:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_356(),
            Matcher_Parser_357()
        ])
class Matcher_Parser_359:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_358())
class Matcher_Parser_360:
    def run(self, stream):
        return stream.match(lambda item: item == 'n', "'n'")
class Matcher_Parser_361:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_360()
        ])
class Matcher_Parser_362:
    def run(self, stream):
        return stream.action(lambda self: '\n')
class Matcher_Parser_363:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_361(),
            Matcher_Parser_362()
        ])
class Matcher_Parser_364:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_363())
class Matcher_Parser_365:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_349(),
            Matcher_Parser_354(),
            Matcher_Parser_359(),
            Matcher_Parser_364()
        ])
class Matcher_Parser_366:
    def run(self, stream):
        return rules['Parser.space'].run(stream)
class Matcher_Parser_367:
    def run(self, stream):
        return rules['Parser.nameStart'].run(stream)
class Matcher_Parser_368:
    def run(self, stream):
        return stream.bind('x', Matcher_Parser_367().run(stream))
class Matcher_Parser_369:
    def run(self, stream):
        return rules['Parser.nameChar'].run(stream)
class Matcher_Parser_370:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_369())
class Matcher_Parser_371:
    def run(self, stream):
        return stream.bind('xs', Matcher_Parser_370().run(stream))
class Matcher_Parser_372:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            self.lookup('x'),
            self.lookup('xs')
        ]))
class Matcher_Parser_373:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_366(),
            Matcher_Parser_368(),
            Matcher_Parser_371(),
            Matcher_Parser_372()
        ])
class Matcher_Parser_374:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_373())
class Matcher_Parser_375:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_374()
        ])
class Matcher_Parser_376:
    def run(self, stream):
        return stream.match(lambda item: 'a' <= item <= 'z', "'a'-'z'")
class Matcher_Parser_377:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_376()
        ])
class Matcher_Parser_378:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_377())
class Matcher_Parser_379:
    def run(self, stream):
        return stream.match(lambda item: 'A' <= item <= 'Z', "'A'-'Z'")
class Matcher_Parser_380:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_379()
        ])
class Matcher_Parser_381:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_380())
class Matcher_Parser_382:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_378(),
            Matcher_Parser_381()
        ])
class Matcher_Parser_383:
    def run(self, stream):
        return stream.match(lambda item: 'a' <= item <= 'z', "'a'-'z'")
class Matcher_Parser_384:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_383()
        ])
class Matcher_Parser_385:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_384())
class Matcher_Parser_386:
    def run(self, stream):
        return stream.match(lambda item: 'A' <= item <= 'Z', "'A'-'Z'")
class Matcher_Parser_387:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_386()
        ])
class Matcher_Parser_388:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_387())
class Matcher_Parser_389:
    def run(self, stream):
        return stream.match(lambda item: '0' <= item <= '9', "'0'-'9'")
class Matcher_Parser_390:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_389()
        ])
class Matcher_Parser_391:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_390())
class Matcher_Parser_392:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_385(),
            Matcher_Parser_388(),
            Matcher_Parser_391()
        ])
class Matcher_Parser_393:
    def run(self, stream):
        return stream.match(lambda item: item == ' ', "' '")
class Matcher_Parser_394:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_393()
        ])
class Matcher_Parser_395:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_394()
        ])
class Matcher_Parser_396:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_395())
class Matcher_Parser_397:
    def run(self, stream):
        return stream.match(lambda item: item == '\n', "'\\n'")
class Matcher_Parser_398:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_397()
        ])
class Matcher_Parser_399:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_398()
        ])
class Matcher_Parser_400:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_399())
class Matcher_Parser_401:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_396(),
            Matcher_Parser_400()
        ])
class Matcher_Parser_402:
    def run(self, stream):
        return stream.operator_star(Matcher_Parser_401())
class Matcher_Parser_403:
    def run(self, stream):
        return stream.operator_and([
            Matcher_Parser_402()
        ])
class Matcher_Parser_404:
    def run(self, stream):
        return stream.with_scope(Matcher_Parser_403())
class Matcher_Parser_405:
    def run(self, stream):
        return stream.operator_or([
            Matcher_Parser_404()
        ])
rules['Parser.file'] = Matcher_Parser_13()
rules['Parser.namespace'] = Matcher_Parser_28()
rules['Parser.rule'] = Matcher_Parser_39()
rules['Parser.choice'] = Matcher_Parser_62()
rules['Parser.sequence'] = Matcher_Parser_71()
rules['Parser.expr'] = Matcher_Parser_97()
rules['Parser.expr1'] = Matcher_Parser_131()
rules['Parser.expr2'] = Matcher_Parser_188()
rules['Parser.matchChar'] = Matcher_Parser_194()
rules['Parser.maybeAction'] = Matcher_Parser_203()
rules['Parser.actionExpr'] = Matcher_Parser_233()
rules['Parser.hostExpr'] = Matcher_Parser_281()
rules['Parser.hostListItem'] = Matcher_Parser_292()
rules['Parser.var'] = Matcher_Parser_305()
rules['Parser.string'] = Matcher_Parser_322()
rules['Parser.char'] = Matcher_Parser_335()
rules['Parser.innerChar'] = Matcher_Parser_344()
rules['Parser.escape'] = Matcher_Parser_365()
rules['Parser.name'] = Matcher_Parser_375()
rules['Parser.nameStart'] = Matcher_Parser_382()
rules['Parser.nameChar'] = Matcher_Parser_392()
rules['Parser.space'] = Matcher_Parser_405()
class Matcher_CodeGenerator_0:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_1:
    def run(self, stream):
        return stream.operator_star(Matcher_CodeGenerator_0())
class Matcher_CodeGenerator_2:
    def run(self, stream):
        return stream.bind('xs', Matcher_CodeGenerator_1().run(stream))
class Matcher_CodeGenerator_3:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_CodeGenerator_4:
    def run(self, stream):
        return stream.operator_not(Matcher_CodeGenerator_3())
class Matcher_CodeGenerator_5:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            self.lookup('xs')
        ]))
class Matcher_CodeGenerator_6:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_2(),
            Matcher_CodeGenerator_4(),
            Matcher_CodeGenerator_5()
        ])
class Matcher_CodeGenerator_7:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_6())
class Matcher_CodeGenerator_8:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_7()
        ])
class Matcher_CodeGenerator_9:
    def run(self, stream):
        return stream.match_call_rule('CodeGenerator')
class Matcher_CodeGenerator_10:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_9().run(stream))
class Matcher_CodeGenerator_11:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_CodeGenerator_12:
    def run(self, stream):
        return stream.operator_not(Matcher_CodeGenerator_11())
class Matcher_CodeGenerator_13:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_10(),
            Matcher_CodeGenerator_12()
        ])
class Matcher_CodeGenerator_14:
    def run(self, stream):
        return stream.match_list(Matcher_CodeGenerator_13())
class Matcher_CodeGenerator_15:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('x'))
class Matcher_CodeGenerator_16:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_14(),
            Matcher_CodeGenerator_15()
        ])
class Matcher_CodeGenerator_17:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_16())
class Matcher_CodeGenerator_18:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_17()
        ])
class Matcher_CodeGenerator_19:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_CodeGenerator_20:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_19().run(stream))
class Matcher_CodeGenerator_21:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_22:
    def run(self, stream):
        return stream.operator_star(Matcher_CodeGenerator_21())
class Matcher_CodeGenerator_23:
    def run(self, stream):
        return stream.bind('ys', Matcher_CodeGenerator_22().run(stream))
class Matcher_CodeGenerator_24:
    def run(self, stream):
        return stream.action(lambda self: self.bind('namespace', self.lookup('x'), lambda: self.bind('ids', self.lookup('concat')([
        
        ]), lambda: self.bind('matchers', self.lookup('concat')([
        
        ]), lambda: self.lookup('join')([
            self.lookup('matchers'),
            self.lookup('ys')
        ])))))
class Matcher_CodeGenerator_25:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_20(),
            Matcher_CodeGenerator_23(),
            Matcher_CodeGenerator_24()
        ])
class Matcher_CodeGenerator_26:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_25())
class Matcher_CodeGenerator_27:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_26()
        ])
class Matcher_CodeGenerator_28:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_CodeGenerator_29:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_28().run(stream))
class Matcher_CodeGenerator_30:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_31:
    def run(self, stream):
        return stream.bind('y', Matcher_CodeGenerator_30().run(stream))
class Matcher_CodeGenerator_32:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            "rules['",
            self.lookup('namespace'),
            '.',
            self.lookup('x'),
            "'] = ",
            self.lookup('y'),
            '\n'
        ]))
class Matcher_CodeGenerator_33:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_29(),
            Matcher_CodeGenerator_31(),
            Matcher_CodeGenerator_32()
        ])
class Matcher_CodeGenerator_34:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_33())
class Matcher_CodeGenerator_35:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_34()
        ])
class Matcher_CodeGenerator_36:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_37:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_36().run(stream))
class Matcher_CodeGenerator_38:
    def run(self, stream):
        return rules['CodeGenerator.astList'].run(stream)
class Matcher_CodeGenerator_39:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_38().run(stream))
class Matcher_CodeGenerator_40:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.operator_or([',
            self.lookup('x'),
            '])'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_41:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_37(),
            Matcher_CodeGenerator_39(),
            Matcher_CodeGenerator_40()
        ])
class Matcher_CodeGenerator_42:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_41())
class Matcher_CodeGenerator_43:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_42()
        ])
class Matcher_CodeGenerator_44:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_45:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_44().run(stream))
class Matcher_CodeGenerator_46:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_47:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_46().run(stream))
class Matcher_CodeGenerator_48:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.with_scope(',
            self.lookup('x'),
            ')'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_49:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_45(),
            Matcher_CodeGenerator_47(),
            Matcher_CodeGenerator_48()
        ])
class Matcher_CodeGenerator_50:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_49())
class Matcher_CodeGenerator_51:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_50()
        ])
class Matcher_CodeGenerator_52:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_53:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_52().run(stream))
class Matcher_CodeGenerator_54:
    def run(self, stream):
        return rules['CodeGenerator.astList'].run(stream)
class Matcher_CodeGenerator_55:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_54().run(stream))
class Matcher_CodeGenerator_56:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.operator_and([',
            self.lookup('x'),
            '])'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_57:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_53(),
            Matcher_CodeGenerator_55(),
            Matcher_CodeGenerator_56()
        ])
class Matcher_CodeGenerator_58:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_57())
class Matcher_CodeGenerator_59:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_58()
        ])
class Matcher_CodeGenerator_60:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_61:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_60().run(stream))
class Matcher_CodeGenerator_62:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_63:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_62().run(stream))
class Matcher_CodeGenerator_64:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_65:
    def run(self, stream):
        return stream.bind('y', Matcher_CodeGenerator_64().run(stream))
class Matcher_CodeGenerator_66:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.bind(',
            self.lookup('x'),
            ', ',
            self.lookup('y'),
            '.run(stream))'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_67:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_61(),
            Matcher_CodeGenerator_63(),
            Matcher_CodeGenerator_65(),
            Matcher_CodeGenerator_66()
        ])
class Matcher_CodeGenerator_68:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_67())
class Matcher_CodeGenerator_69:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_68()
        ])
class Matcher_CodeGenerator_70:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_71:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_70().run(stream))
class Matcher_CodeGenerator_72:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_73:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_72().run(stream))
class Matcher_CodeGenerator_74:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.operator_star(',
            self.lookup('x'),
            ')'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_75:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_71(),
            Matcher_CodeGenerator_73(),
            Matcher_CodeGenerator_74()
        ])
class Matcher_CodeGenerator_76:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_75())
class Matcher_CodeGenerator_77:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_76()
        ])
class Matcher_CodeGenerator_78:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_79:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_78().run(stream))
class Matcher_CodeGenerator_80:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_81:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_80().run(stream))
class Matcher_CodeGenerator_82:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.operator_not(',
            self.lookup('x'),
            ')'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_83:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_79(),
            Matcher_CodeGenerator_81(),
            Matcher_CodeGenerator_82()
        ])
class Matcher_CodeGenerator_84:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_83())
class Matcher_CodeGenerator_85:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_84()
        ])
class Matcher_CodeGenerator_86:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_87:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_86().run(stream))
class Matcher_CodeGenerator_88:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            "stream.match_call_rule('",
            self.lookup('namespace'),
            "')"
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_89:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_87(),
            Matcher_CodeGenerator_88()
        ])
class Matcher_CodeGenerator_90:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_89())
class Matcher_CodeGenerator_91:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_90()
        ])
class Matcher_CodeGenerator_92:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_93:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_92().run(stream))
class Matcher_CodeGenerator_94:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_CodeGenerator_95:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_94().run(stream))
class Matcher_CodeGenerator_96:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            "rules['",
            self.lookup('namespace'),
            '.',
            self.lookup('x'),
            "'].run(stream)"
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_97:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_93(),
            Matcher_CodeGenerator_95(),
            Matcher_CodeGenerator_96()
        ])
class Matcher_CodeGenerator_98:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_97())
class Matcher_CodeGenerator_99:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_98()
        ])
class Matcher_CodeGenerator_100:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_101:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_100().run(stream))
class Matcher_CodeGenerator_102:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_103:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_102().run(stream))
class Matcher_CodeGenerator_104:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.match(lambda item: ',
            self.lookup('x'),
            ')'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_105:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_101(),
            Matcher_CodeGenerator_103(),
            Matcher_CodeGenerator_104()
        ])
class Matcher_CodeGenerator_106:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_105())
class Matcher_CodeGenerator_107:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_106()
        ])
class Matcher_CodeGenerator_108:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_109:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_108().run(stream))
class Matcher_CodeGenerator_110:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_111:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_110().run(stream))
class Matcher_CodeGenerator_112:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.match_list(',
            self.lookup('x'),
            ')'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_113:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_109(),
            Matcher_CodeGenerator_111(),
            Matcher_CodeGenerator_112()
        ])
class Matcher_CodeGenerator_114:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_113())
class Matcher_CodeGenerator_115:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_114()
        ])
class Matcher_CodeGenerator_116:
    def run(self, stream):
        return rules['CodeGenerator.matcher'].run(stream)
class Matcher_CodeGenerator_117:
    def run(self, stream):
        return stream.bind('m', Matcher_CodeGenerator_116().run(stream))
class Matcher_CodeGenerator_118:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_119:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_118().run(stream))
class Matcher_CodeGenerator_120:
    def run(self, stream):
        return stream.action(lambda self: self.bind('body', self.lookup('join')([
            'stream.action(lambda self: ',
            self.lookup('x'),
            ')'
        ]), lambda: self.lookup('m')))
class Matcher_CodeGenerator_121:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_117(),
            Matcher_CodeGenerator_119(),
            Matcher_CodeGenerator_120()
        ])
class Matcher_CodeGenerator_122:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_121())
class Matcher_CodeGenerator_123:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_122()
        ])
class Matcher_CodeGenerator_124:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            'True',
            ", 'any'"
        ]))
class Matcher_CodeGenerator_125:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_124()
        ])
class Matcher_CodeGenerator_126:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_125())
class Matcher_CodeGenerator_127:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_126()
        ])
class Matcher_CodeGenerator_128:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_129:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_128().run(stream))
class Matcher_CodeGenerator_130:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            'item == ',
            self.lookup('x'),
            ', ',
            self.lookup('repr')(
                self.lookup('x')
            )
        ]))
class Matcher_CodeGenerator_131:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_129(),
            Matcher_CodeGenerator_130()
        ])
class Matcher_CodeGenerator_132:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_131())
class Matcher_CodeGenerator_133:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_132()
        ])
class Matcher_CodeGenerator_134:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_135:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_134().run(stream))
class Matcher_CodeGenerator_136:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_137:
    def run(self, stream):
        return stream.bind('y', Matcher_CodeGenerator_136().run(stream))
class Matcher_CodeGenerator_138:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            self.lookup('x'),
            ' <= item <= ',
            self.lookup('y'),
            ', "',
            self.lookup('x'),
            '-',
            self.lookup('y'),
            '"'
        ]))
class Matcher_CodeGenerator_139:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_135(),
            Matcher_CodeGenerator_137(),
            Matcher_CodeGenerator_138()
        ])
class Matcher_CodeGenerator_140:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_139())
class Matcher_CodeGenerator_141:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_140()
        ])
class Matcher_CodeGenerator_142:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_143:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_142().run(stream))
class Matcher_CodeGenerator_144:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_145:
    def run(self, stream):
        return stream.bind('y', Matcher_CodeGenerator_144().run(stream))
class Matcher_CodeGenerator_146:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_147:
    def run(self, stream):
        return stream.bind('z', Matcher_CodeGenerator_146().run(stream))
class Matcher_CodeGenerator_148:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            'self.bind(',
            self.lookup('x'),
            ', ',
            self.lookup('y'),
            ', lambda: ',
            self.lookup('z'),
            ')'
        ]))
class Matcher_CodeGenerator_149:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_143(),
            Matcher_CodeGenerator_145(),
            Matcher_CodeGenerator_147(),
            Matcher_CodeGenerator_148()
        ])
class Matcher_CodeGenerator_150:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_149())
class Matcher_CodeGenerator_151:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_150()
        ])
class Matcher_CodeGenerator_152:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_153:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_152()
        ])
class Matcher_CodeGenerator_154:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_153())
class Matcher_CodeGenerator_155:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_154()
        ])
class Matcher_CodeGenerator_156:
    def run(self, stream):
        return rules['CodeGenerator.astList'].run(stream)
class Matcher_CodeGenerator_157:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_156().run(stream))
class Matcher_CodeGenerator_158:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            "self.lookup('concat')([",
            self.lookup('x'),
            '])'
        ]))
class Matcher_CodeGenerator_159:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_157(),
            Matcher_CodeGenerator_158()
        ])
class Matcher_CodeGenerator_160:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_159())
class Matcher_CodeGenerator_161:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_160()
        ])
class Matcher_CodeGenerator_162:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_163:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_162().run(stream))
class Matcher_CodeGenerator_164:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_165:
    def run(self, stream):
        return stream.bind('y', Matcher_CodeGenerator_164().run(stream))
class Matcher_CodeGenerator_166:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            "self.lookup('splice')(",
            self.lookup('x'),
            ', ',
            self.lookup('y'),
            ')'
        ]))
class Matcher_CodeGenerator_167:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_163(),
            Matcher_CodeGenerator_165(),
            Matcher_CodeGenerator_166()
        ])
class Matcher_CodeGenerator_168:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_167())
class Matcher_CodeGenerator_169:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_168()
        ])
class Matcher_CodeGenerator_170:
    def run(self, stream):
        return rules['CodeGenerator.astList'].run(stream)
class Matcher_CodeGenerator_171:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_170().run(stream))
class Matcher_CodeGenerator_172:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            "self.lookup('join')([",
            self.lookup('x'),
            '])'
        ]))
class Matcher_CodeGenerator_173:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_171(),
            Matcher_CodeGenerator_172()
        ])
class Matcher_CodeGenerator_174:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_173())
class Matcher_CodeGenerator_175:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_174()
        ])
class Matcher_CodeGenerator_176:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_177:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_176().run(stream))
class Matcher_CodeGenerator_178:
    def run(self, stream):
        return rules['CodeGenerator.astList'].run(stream)
class Matcher_CodeGenerator_179:
    def run(self, stream):
        return stream.bind('y', Matcher_CodeGenerator_178().run(stream))
class Matcher_CodeGenerator_180:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            self.lookup('x'),
            '(',
            self.lookup('y'),
            ')'
        ]))
class Matcher_CodeGenerator_181:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_177(),
            Matcher_CodeGenerator_179(),
            Matcher_CodeGenerator_180()
        ])
class Matcher_CodeGenerator_182:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_181())
class Matcher_CodeGenerator_183:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_182()
        ])
class Matcher_CodeGenerator_184:
    def run(self, stream):
        return rules['CodeGenerator.repr'].run(stream)
class Matcher_CodeGenerator_185:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_184().run(stream))
class Matcher_CodeGenerator_186:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            'self.lookup(',
            self.lookup('x'),
            ')'
        ]))
class Matcher_CodeGenerator_187:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_185(),
            Matcher_CodeGenerator_186()
        ])
class Matcher_CodeGenerator_188:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_187())
class Matcher_CodeGenerator_189:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_188()
        ])
class Matcher_CodeGenerator_190:
    def run(self, stream):
        return rules['CodeGenerator.ast'].run(stream)
class Matcher_CodeGenerator_191:
    def run(self, stream):
        return stream.operator_star(Matcher_CodeGenerator_190())
class Matcher_CodeGenerator_192:
    def run(self, stream):
        return stream.bind('xs', Matcher_CodeGenerator_191().run(stream))
class Matcher_CodeGenerator_193:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('join')([
            '\n',
            self.lookup('indent')(
                self.lookup('join')(
                    self.lookup('xs'),
                    ',\n'
                )
            ),
            '\n'
        ]))
class Matcher_CodeGenerator_194:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_192(),
            Matcher_CodeGenerator_193()
        ])
class Matcher_CodeGenerator_195:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_194())
class Matcher_CodeGenerator_196:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_195()
        ])
class Matcher_CodeGenerator_197:
    def run(self, stream):
        return stream.action(lambda self: self.bind('id', self.lookup('join')([
            'Matcher_',
            self.lookup('namespace'),
            '_',
            self.lookup('len')(
                self.lookup('ids')
            )
        ]), lambda: self.bind('', self.lookup('append')(
            self.lookup('ids'),
            self.lookup('id')
        ), lambda: self.bind('', self.lookup('append')(
            self.lookup('matchers'),
            self.lookup('join')([
                'class ',
                self.lookup('id'),
                ':\n',
                self.lookup('indent')(
                    self.lookup('join')([
                        'def run(self, stream):\n',
                        self.lookup('indent')(
                            self.lookup('join')([
                                'return ',
                                self.lookup('body'),
                                '\n'
                            ])
                        )
                    ])
                )
            ])
        ), lambda: self.lookup('join')([
            self.lookup('id'),
            '()'
        ])))))
class Matcher_CodeGenerator_198:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_197()
        ])
class Matcher_CodeGenerator_199:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_198())
class Matcher_CodeGenerator_200:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_199()
        ])
class Matcher_CodeGenerator_201:
    def run(self, stream):
        return stream.match(lambda item: True, 'any')
class Matcher_CodeGenerator_202:
    def run(self, stream):
        return stream.bind('x', Matcher_CodeGenerator_201().run(stream))
class Matcher_CodeGenerator_203:
    def run(self, stream):
        return stream.action(lambda self: self.lookup('repr')(
            self.lookup('x')
        ))
class Matcher_CodeGenerator_204:
    def run(self, stream):
        return stream.operator_and([
            Matcher_CodeGenerator_202(),
            Matcher_CodeGenerator_203()
        ])
class Matcher_CodeGenerator_205:
    def run(self, stream):
        return stream.with_scope(Matcher_CodeGenerator_204())
class Matcher_CodeGenerator_206:
    def run(self, stream):
        return stream.operator_or([
            Matcher_CodeGenerator_205()
        ])
rules['CodeGenerator.asts'] = Matcher_CodeGenerator_8()
rules['CodeGenerator.ast'] = Matcher_CodeGenerator_18()
rules['CodeGenerator.Namespace'] = Matcher_CodeGenerator_27()
rules['CodeGenerator.Rule'] = Matcher_CodeGenerator_35()
rules['CodeGenerator.Or'] = Matcher_CodeGenerator_43()
rules['CodeGenerator.Scope'] = Matcher_CodeGenerator_51()
rules['CodeGenerator.And'] = Matcher_CodeGenerator_59()
rules['CodeGenerator.Bind'] = Matcher_CodeGenerator_69()
rules['CodeGenerator.Star'] = Matcher_CodeGenerator_77()
rules['CodeGenerator.Not'] = Matcher_CodeGenerator_85()
rules['CodeGenerator.MatchCallRule'] = Matcher_CodeGenerator_91()
rules['CodeGenerator.MatchRule'] = Matcher_CodeGenerator_99()
rules['CodeGenerator.MatchObject'] = Matcher_CodeGenerator_107()
rules['CodeGenerator.MatchList'] = Matcher_CodeGenerator_115()
rules['CodeGenerator.Action'] = Matcher_CodeGenerator_123()
rules['CodeGenerator.Any'] = Matcher_CodeGenerator_127()
rules['CodeGenerator.Eq'] = Matcher_CodeGenerator_133()
rules['CodeGenerator.Range'] = Matcher_CodeGenerator_141()
rules['CodeGenerator.Set'] = Matcher_CodeGenerator_151()
rules['CodeGenerator.String'] = Matcher_CodeGenerator_155()
rules['CodeGenerator.List'] = Matcher_CodeGenerator_161()
rules['CodeGenerator.ListItem'] = Matcher_CodeGenerator_169()
rules['CodeGenerator.Format'] = Matcher_CodeGenerator_175()
rules['CodeGenerator.Call'] = Matcher_CodeGenerator_183()
rules['CodeGenerator.Lookup'] = Matcher_CodeGenerator_189()
rules['CodeGenerator.astList'] = Matcher_CodeGenerator_196()
rules['CodeGenerator.matcher'] = Matcher_CodeGenerator_200()
rules['CodeGenerator.repr'] = Matcher_CodeGenerator_206()
if __name__ == "__main__":
    import sys
    def read(path):
        if path == "-":
            return sys.stdin.read()
        with open(path) as f:
            return f.read()
    args = sys.argv[1:] or ["--compile", "-"]
    while args:
        command = args.pop(0)
        if command == "--support":
            sys.stdout.write(SUPPORT)
        elif command == "--copy":
            sys.stdout.write(read(args.pop(0)))
        elif command == "--embed":
            sys.stdout.write("{} = {}\n".format(
                args.pop(0),
                repr(read(args.pop(0)))
            ))
        elif command == "--compile":
            sys.stdout.write(compile_chain(
                ["Parser.file", "CodeGenerator.asts"],
                read(args.pop(0))
            ))
        else:
            sys.exit("ERROR: Unknown command '{}'".format(command))
