import antlr4
from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from dbgpt.storage.knowledge_graph.community.base import QuerySyntaxValidator
from dbgpt.storage.knowledge_graph.community.tugraph_cypher_parser.LcypherLexer import LcypherLexer
from dbgpt.storage.knowledge_graph.community.tugraph_cypher_parser.LcypherParser import LcypherParser


class MyErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise Exception(
            "ERROR: when parsing line %d column %d: %s\n" % (line, column, msg)
        )


class TuGraphSyntaxValidator(GraphSyntaxValidator):
    """TuGraph Community Syntax Validator."""

    def validate(self, query: str) -> bool:
        error_listener = MyErrorListener()
        try:
            input_stream = InputStream(query)
            lexer = LcypherLexer(input_stream)
            lexer.removeErrorListeners()
            lexer.addErrorListener(error_listener)
            stream = CommonTokenStream(lexer)
            parser = LcypherParser(stream)
            parser.removeErrorListeners()
            parser.addErrorListener(error_listener)
            tree = parser.oC_Cypher()
            return True
        except Exception as e:
            return False
