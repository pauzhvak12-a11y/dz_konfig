from __future__ import annotations

import json
import sys

from config_lang import LexError, ParseError, parse_config


def main() -> int:
    """Точка входа CLI.

    Читает исходный текст с stdin, печатает JSON в stdout.
    В случае ошибки выводит сообщение в stderr и возвращает код 1.
    """
    src = sys.stdin.read()
    try:
        data = parse_config(src)
    except (LexError, ParseError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()  # завершающий перевод строки
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


