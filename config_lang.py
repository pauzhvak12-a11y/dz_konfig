"""
Учебный конфигурационный язык (вариант №28).

Поддерживаемые конструкции из условия:

- Многострочные комментарии: {{! ... }}
- Числа: 0[o0][0-7]+ (восьмеричные) и одиночный 0.
- Массивы: list( значение, значение, ... )
- Словари:
    begin
        имя := значение;
        ...
    end
- Имена (идентификаторы): [a-z][a-z0-9_]*
- Объявления констант на этапе трансляции:
    имя = значение

Программа состоит из набора объявлений констант. На выходе
получаем JSON‑объект, где ключи — имена констант, значения —
вычисленные значения (числа, массивы, словари).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class LexError(Exception):
    pass


class ParseError(Exception):
    pass


@dataclass
class Token:
    kind: str
    value: str
    line: int
    col: int

    def __repr__(self) -> str:  # pragma: no cover - для отладки
        return f"Token({self.kind!r}, {self.value!r}, {self.line}:{self.col})"


KEYWORDS = {"list", "begin", "end"}


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    def _peek(self, n: int = 0) -> str:
        idx = self.pos + n
        return self.text[idx] if idx < len(self.text) else ""

    def _advance(self, n: int = 1) -> None:
        for _ in range(n):
            if self.pos >= len(self.text):
                return
            ch = self.text[self.pos]
            self.pos += 1
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1

    def tokens(self) -> List[Token]:
        result: List[Token] = []
        while True:
            tok = self._next_token()
            if tok is None:
                break
            result.append(tok)
        return result

    def _skip_ws_and_comments(self) -> None:
        while True:
            # пропуск пробелов и переводов строк
            while self._peek() and self._peek().isspace():
                self._advance()

            # многострочные комментарии {{! ... }}
            if self._peek() == "{" and self._peek(1) == "{" and self._peek(2) == "!":
                # запоминаем позицию на случай незакрытого комментария
                start_line, start_col = self.line, self.col
                self._advance(3)  # '{{!'
                while True:
                    if not self._peek():
                        raise LexError(
                            f"Незакрытый комментарий, начало на {start_line}:{start_col}"
                        )
                    if self._peek() == "}" and self._peek(1) == "}":
                        self._advance(2)
                        break
                    self._advance()
                continue

            break

    def _next_token(self) -> Optional[Token]:
        self._skip_ws_and_comments()
        ch = self._peek()
        if not ch:
            return None

        start_line, start_col = self.line, self.col

        # идентификаторы и ключевые слова
        if "a" <= ch <= "z":
            ident = []
            while True:
                ch2 = self._peek()
                if not ch2 or not (
                    "a" <= ch2 <= "z" or "0" <= ch2 <= "9" or ch2 == "_"
                ):
                    break
                ident.append(ch2)
                self._advance()
            value = "".join(ident)
            kind = "KW" if value in KEYWORDS else "IDENT"
            return Token(kind, value, start_line, start_col)

        # числа: 0 или 0[o0][0-7]+
        if ch == "0":
            lexeme = []
            while True:
                ch2 = self._peek()
                if not ch2 or not (
                    ch2 == "0"
                    or ch2 == "o"
                    or ch2 == "O"
                    or ("0" <= ch2 <= "7")
                ):
                    break
                lexeme.append(ch2)
                self._advance()
            value = "".join(lexeme)
            # Простая проверка по шаблону
            if value == "0":
                return Token("NUMBER", value, start_line, start_col)
            if len(value) >= 3 and value[0] == "0" and value[1] in ("o", "O", "0"):
                # 0[o0][0-7]+
                digits = value[2:]
                if not digits or any(d not in "01234567" for d in digits):
                    raise LexError(
                        f"Некорректное восьмеричное число '{value}' на {start_line}:{start_col}"
                    )
                return Token("NUMBER", value, start_line, start_col)
            raise LexError(
                f"Число должно быть вида 0 или 0[o0][0-7]+, найдено '{value}' на {start_line}:{start_col}"
            )

        # односимвольные токены
        single = {
            "(": "LPAREN",
            ")": "RPAREN",
            ",": "COMMA",
            ";": "SEMICOLON",
            "=": "EQUAL",
        }
        if ch in single:
            self._advance()
            return Token(single[ch], ch, start_line, start_col)

        # двусимвольный токен ':='
        if ch == ":" and self._peek(1) == "=":
            self._advance(2)
            return Token("ASSIGN", ":=", start_line, start_col)

        raise LexError(f"Неожиданный символ '{ch}' на {start_line}:{start_col}")


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.consts: Dict[str, Any] = {}

    def _peek(self, k: int = 0) -> Optional[Token]:
        idx = self.pos + k
        return self.tokens[idx] if idx < len(self.tokens) else None

    def _advance(self) -> Token:
        tok = self._peek()
        if tok is None:
            raise ParseError("Неожиданный конец ввода")
        self.pos += 1
        return tok

    def _expect(self, kind: str, value: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok is None:
            raise ParseError(f"Ожидалось {kind}, но вход закончился")
        if tok.kind != kind:
            raise ParseError(
                f"Ожидалось {kind}, а найдено {tok.kind} '{tok.value}' на {tok.line}:{tok.col}"
            )
        if value is not None and tok.value != value:
            raise ParseError(
                f"Ожидалось '{value}', а найдено '{tok.value}' на {tok.line}:{tok.col}"
            )
        self.pos += 1
        return tok

    # === Внешний интерфейс ===

    def parse_program(self) -> Dict[str, Any]:
        while self._peek() is not None:
            self._parse_const_declaration()
        return self.consts

    # === Правила грамматики ===

    def _parse_const_declaration(self) -> None:
        name_tok = self._expect("IDENT")
        name = name_tok.value
        if name in self.consts:
            raise ParseError(
                f"Константа '{name}' уже объявлена (строка {name_tok.line}, столбец {name_tok.col})"
            )
        self._expect("EQUAL")
        value = self._parse_expr()
        # простая защита от рекурсивных ссылок: значение уже вычислено, а
        # в выражении можно ссылаться только на ранее объявленные константы
        self.consts[name] = value

    def _parse_expr(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ParseError("Ожидалось выражение, но вход закончился")

        if tok.kind == "NUMBER":
            self._advance()
            return self._number_value(tok.value)

        if tok.kind == "KW" and tok.value == "list":
            return self._parse_list()

        if tok.kind == "KW" and tok.value == "begin":
            return self._parse_dict()

        if tok.kind == "IDENT":
            # ссылка на ранее объявленную константу
            self._advance()
            name = tok.value
            if name not in self.consts:
                raise ParseError(
                    f"Использование необъявленной константы '{name}' на {tok.line}:{tok.col}"
                )
            return self.consts[name]

        raise ParseError(
            f"Ожидалось число, list(...), begin ... end или имя константы, найдено '{tok.value}' на {tok.line}:{tok.col}"
        )

    def _parse_list(self) -> List[Any]:
        self._expect("KW", "list")
        self._expect("LPAREN")
        items: List[Any] = []
        # допускаем пустой список: list()
        if self._peek() and self._peek().kind != "RPAREN":
            items.append(self._parse_expr())
            while self._peek() and self._peek().kind == "COMMA":
                self._advance()
                items.append(self._parse_expr())
        self._expect("RPAREN")
        return items

    def _parse_dict(self) -> Dict[str, Any]:
        self._expect("KW", "begin")
        result: Dict[str, Any] = {}
        while True:
            tok = self._peek()
            if tok is None:
                raise ParseError("Ожидался 'end' для словаря, но вход закончился")
            if tok.kind == "KW" and tok.value == "end":
                self._advance()
                break
            key_tok = self._expect("IDENT")
            key = key_tok.value
            if key in result:
                raise ParseError(
                    f"Ключ '{key}' в словаре уже использован (строка {key_tok.line}, столбец {key_tok.col})"
                )
            self._expect("ASSIGN")
            value = self._parse_expr()
            self._expect("SEMICOLON")
            result[key] = value
        return result

    # === Вспомогательные методы ===

    @staticmethod
    def _number_value(lexeme: str) -> int:
        """Преобразует лексему числа в целое значение."""
        if lexeme == "0":
            return 0
        # формат 0[o0][0-7]+ — берём часть после первых двух символов
        digits = lexeme[2:]
        return int(digits, 8)


def parse_config(text: str) -> Dict[str, Any]:
    """Высокоуровневая функция: текст -> словарь констант."""
    lexer = Lexer(text)
    tokens = lexer.tokens()
    parser = Parser(tokens)
    return parser.parse_program()


__all__ = ["LexError", "ParseError", "parse_config"]


