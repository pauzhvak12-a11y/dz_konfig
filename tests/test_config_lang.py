from __future__ import annotations

import os
import unittest

from config_lang import LexError, ParseError, parse_config


class ConfigLangBasicTests(unittest.TestCase):
    def test_number_zero_and_octal(self) -> None:
        src = "a = 0\nb = 0o10\nc = 0007\n"
        result = parse_config(src)
        self.assertEqual(result["a"], 0)
        self.assertEqual(result["b"], 8)
        self.assertEqual(result["c"], 7)

    def test_invalid_number_raises(self) -> None:
        src = "a = 09\n"
        with self.assertRaises(LexError):
            parse_config(src)

    def test_list_and_nested_values(self) -> None:
        src = """
        base = 0o2
        values = list(0, base, list(base))
        """
        result = parse_config(src)
        self.assertEqual(result["base"], 2)
        self.assertEqual(result["values"], [0, 2, [2]])

    def test_dict_with_nested_structures(self) -> None:
        src = """
        num = 0o5
        arr = list(num, 0)
        obj = begin
          value := num;
          list_value := arr;
          inner := begin
            x := 0;
          end;
        end
        """
        result = parse_config(src)
        obj = result["obj"]
        self.assertEqual(obj["value"], 5)
        self.assertEqual(obj["list_value"], [5, 0])
        self.assertEqual(obj["inner"]["x"], 0)

    def test_comments_are_ignored(self) -> None:
        src = """
        {{! многострочный
        комментарий }}
        x = 0
        """
        result = parse_config(src)
        self.assertEqual(result["x"], 0)

    def test_const_reference_and_shadowing_error(self) -> None:
        src_ok = """
        a = 0o7
        b = a
        """
        result = parse_config(src_ok)
        self.assertEqual(result["b"], 7)

        src_dup = """
        a = 0
        a = 0
        """
        with self.assertRaises(ParseError):
            parse_config(src_dup)

    def test_undeclared_const_usage_raises(self) -> None:
        src = "a = b"
        with self.assertRaises(ParseError):
            parse_config(src)


class ExampleConfigsTests(unittest.TestCase):
    def _read_example(self, name: str) -> str:
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "examples", name)
        with open(path, "r", encoding="utf8") as f:
            return f.read()

    def test_web_server_example(self) -> None:
        src = self._read_example("web_server.conf")
        result = parse_config(src)

        # проверяем несколько ключевых моментов, но не все поля
        self.assertIn("server", result)
        server = result["server"]
        self.assertIn("ports", server)
        self.assertIsInstance(server["ports"], list)

    def test_iot_device_example(self) -> None:
        src = self._read_example("iot_device.conf")
        result = parse_config(src)

        self.assertIn("device", result)
        device = result["device"]
        self.assertIn("sensors", device)
        self.assertIsInstance(device["sensors"], list)


if __name__ == "__main__":
    unittest.main()


