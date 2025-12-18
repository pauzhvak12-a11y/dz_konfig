"""
Учебный конфигурационный язык (вариант №28).

Требования из задания соблюдены, используется
специализированный инструмент синтаксического разбора — Lark.

Поддерживаемые конструкции:
- Многострочные комментарии: {{! ... }}
- Числа: 0[o0][0-7]+ (восьмеричные) и одиночный 0.
- Массивы: list( значение, значение, ... )
- Словари:
    begin
        имя := значение;
        ...
    end
- Имена (идентификаторы): [a-z][a-z0-9_]*
- Объявления констант (программа — это набор таких строк):
    имя = значение
  В правой части можно ссылаться на ранее объявленные константы.
На выходе формируется JSON‑объект: ключи — имена констант, значения —
вычисленные выражения.
"""

from __future__ import annotations

from typing import Any, Dict, List

from lark import Lark, Transformer
from lark.exceptions import UnexpectedCharacters, UnexpectedInput


class LexError(Exception):
    """Ошибки лексического анализа."""


class ParseError(Exception):
    """Ошибки синтаксического анализа или семантики."""


GRAMMAR = r"""
    start: stmt+

    stmt: IDENT "=" expr      -> assign

    ?expr: NUMBER             -> number
         | "list" "(" [expr ("," expr)*] ")"   -> list
         | "begin" dict_item* "end"            -> dict
         | IDENT                               -> ident

    dict_item: IDENT ":=" expr ";"             -> dict_pair

    // Числа: 0 или восьмеричные с опциональным префиксом o/O, допускаем лидирующие нули.
    NUMBER: "0" | "0" ("o"|"O")? ("0".."7")+
    IDENT: /[a-z][a-z0-9_]*/

    COMMENT: /{{![\s\S]*?}}/

    %import common.WS
    %ignore WS
    %ignore COMMENT
"""


class _AstBuilder(Transformer):
    """Преобразует дерево Lark в простой Python AST."""

    def start(self, items: List[Any]) -> List[Any]:
        return items

    def assign(self, items: List[Any]) -> Dict[str, Any]:
        name, expr = items
        return {"type": "assign", "name": name, "expr": expr}

    def number(self, items: List[Any]) -> Dict[str, Any]:
        (token,) = items
        return {"type": "number", "value": str(token)}

    def ident(self, items: List[Any]) -> Dict[str, Any]:
        (token,) = items
        return {"type": "ident", "name": str(token)}

    def list(self, items: List[Any]) -> Dict[str, Any]:
        return {"type": "list", "items": items}

    def dict(self, items: List[Any]) -> Dict[str, Any]:
        return {"type": "dict", "items": items}

    def dict_pair(self, items: List[Any]) -> Dict[str, Any]:
        key, value = items
        return {"key": key, "value": value}

    def IDENT(self, token):  # type: ignore[override]
        return str(token)

    def NUMBER(self, token):  # type: ignore[override]
        return str(token)


_parser = Lark(GRAMMAR, parser="lalr", start="start", propagate_positions=True)


def _number_value(lexeme: str) -> int:
    """Преобразует лексему числа в целое значение."""
    if lexeme == "0":
        return 0
    # если второй символ o/O — отбрасываем префикс, иначе берём всё после ведущего нуля
    if len(lexeme) >= 2 and lexeme[1] in ("o", "O"):
        digits = lexeme[2:]
    else:
        digits = lexeme[1:]
    return int(digits, 8)


def _eval_expr(node: Dict[str, Any], env: Dict[str, Any]) -> Any:
    ntype = node["type"]

    if ntype == "number":
        return _number_value(node["value"])

    if ntype == "ident":
        name = node["name"]
        if name not in env:
            raise ParseError(f"Использование необъявленной константы '{name}'")
        return env[name]

    if ntype == "list":
        return [_eval_expr(item, env) for item in node["items"]]

    if ntype == "dict":
        result: Dict[str, Any] = {}
        for pair in node["items"]:
            key = pair["key"]
            if key in result:
                raise ParseError(f"Ключ '{key}' в словаре уже использован")
            result[key] = _eval_expr(pair["value"], env)
        return result

    raise ParseError(f"Неизвестный тип узла: {ntype}")


def parse_config(text: str) -> Dict[str, Any]:
    """Высокоуровневая функция: текст -> словарь констант.
    Использует Lark для синтаксического разбора."""
    try:
        tree = _parser.parse(text)
    except UnexpectedCharacters as exc:
        raise LexError(str(exc)) from exc
    except UnexpectedInput as exc:
        # все прочие ошибки разбора считаем синтаксическими
        raise ParseError(str(exc)) from exc

    ast = _AstBuilder().transform(tree)

    env: Dict[str, Any] = {}
    for stmt in ast:
        name = stmt["name"]
        if name in env:
            raise ParseError(f"Константа '{name}' уже объявлена")
        value = _eval_expr(stmt["expr"], env)
        env[name] = value

    return env


__all__ = ["LexError", "ParseError", "parse_config"]

