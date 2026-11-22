# -*- coding: utf-8 -*-
"""CLI ru_simplifier (Фаза 0 — analyze; упрощение появится в Фазах 3+).

Использование (Windows, из корня проекта):
    python -m ru_simplifier analyze --text "Хотя мечте Петра..."
    python -m ru_simplifier analyze --file input.txt --out analysis.json [--pretty]

Кодировка ввода/вывода — UTF-8 явно (Windows cp1251-safe).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ru_simplifier",
        description="Детерминированный анализатор/упрощатель русского текста "
                    "(Фазы 0-1: только analyze).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    ap = sub.add_parser("analyze", help="Разобрать текст до AnalyzedSentence (JSON)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", type=str, help="Текст для анализа")
    src.add_argument("--file", type=Path, help="Путь к файлу с текстом (UTF-8)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Куда записать JSON (по умолчанию — stdout)")
    ap.add_argument("--pretty", action="store_true", help="Отступы 2 пробела")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "analyze":
        # Импорт здесь, чтобы --help не грузил модели.
        from ru_simplifier.pipeline import analyze_text

        if args.text is not None:
            text = args.text
        else:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()

        result = analyze_text(text)
        indent = 2 if args.pretty else None
        payload = json.dumps(result, ensure_ascii=False, indent=indent)

        if args.out is None:
            # Windows-совместимый вывод кириллицы в консоль
            try:
                sys.stdout.reconfigure(encoding="utf-8")  # py3.7+
            except Exception:
                pass
            print(payload)
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(payload)
            print(f"OK: записано {args.out}", file=sys.stderr)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
