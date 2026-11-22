"""Запуск Splice: python main.py [--mode chop|merge] [файлы…]

Вся логика старта — в splice/bootstrap.py, чтобы `python -m splice` и собранный
exe шли ровно тем же путём.
"""

from splice.bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
