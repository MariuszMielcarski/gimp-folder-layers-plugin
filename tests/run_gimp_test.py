"""Uruchamia test pluginu w osobnej instancji GIMP."""
import argparse
from pathlib import Path
import subprocess


# Uruchamia test przez stdin i sprawdza znacznik sukcesu niezależnie od kodu wyjścia Gimpa.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gimp', required=True)
    parser.add_argument('--report', help='Opcjonalny plik raportu testu')
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    code = (Path(__file__).with_name('gimp_smoke.py')).read_text(encoding='utf-8')
    result = subprocess.run([
        arguments.gimp, '--no-interface', '--no-splash', '--new-instance',
        '--batch-interpreter=python-fu-eval', '--batch=-', '--quit'
    ], input=code, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=root, timeout=90)
    print(result.stdout)
    print(result.stderr)
    if arguments.report:
        Path(arguments.report).write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode or 'PASS GIMP integration:' not in result.stdout + result.stderr:
        raise SystemExit('Test integracyjny Gimpa nie przeszedł.')


if __name__ == '__main__':
    main()