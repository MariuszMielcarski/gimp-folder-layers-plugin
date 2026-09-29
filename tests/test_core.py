import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'folder-layers' / 'folder_layers_core.py'
SPEC = importlib.util.spec_from_file_location('folder_core', MODULE)
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)
PNG = b'\x89PNG\r\n\x1a\nfixture'


class SyncTests(unittest.TestCase):
    # Tworzy odizolowany katalog i katalog eksportów.
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.stage = self.folder / '.stage'
        self.stage.mkdir()
        (self.folder / 'a.png').write_bytes(PNG + b'a')
        (self.folder / 'b.png').write_bytes(PNG + b'b')
        self.baseline = core.scan(self.folder)

    # Przygotowuje plik eksportu do transakcji.
    def staged(self, name, data):
        path = self.stage / name
        path.write_bytes(data)
        return path

    # Sprawdza zmianę nazwy, usunięcie i zachowanie obcych plików.
    def test_rename_delete_and_unrelated(self):
        (self.folder / 'outside.png').write_bytes(PNG + b'outside')
        result = core.commit(self.folder, self.baseline, {'renamed.png': self.staged('new.png', PNG + b'a')})
        self.assertEqual(list(result), ['renamed.png'])
        self.assertFalse((self.folder / 'a.png').exists())
        self.assertFalse((self.folder / 'b.png').exists())
        self.assertTrue((self.folder / 'outside.png').exists())
        self.assertEqual(len(list((self.folder / '.trash').glob('*/*.png'))), 2)

    # Sprawdza zamianę nazw istniejących plików bez utraty zawartości.
    def test_swap(self):
        core.commit(self.folder, self.baseline, {
            'b.png': self.staged('first.png', PNG + b'a'),
            'a.png': self.staged('second.png', PNG + b'b')})
        self.assertEqual((self.folder / 'b.png').read_bytes(), PNG + b'a')
        self.assertEqual((self.folder / 'a.png').read_bytes(), PNG + b'b')

    # Sprawdza nazwy niedozwolone w Windows i kolizje wielkości liter.
    def test_invalid_names(self):
        for name in ('../evil', 'CON', 'con.test.png', 'a:b', 'a?', 'a.', 'a ', '', '/file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                core.filename(name)
        with self.assertRaises(ValueError):
            core.validate(self.folder, self.baseline, ['A.png', 'a.png'])

    # Zatrzymuje zapis po modyfikacji źródła poza Gimpem.
    def test_external_change(self):
        (self.folder / 'a.png').write_bytes(PNG + b'external')
        with self.assertRaises(ValueError):
            core.commit(self.folder, self.baseline, {})
        self.assertEqual((self.folder / 'a.png').read_bytes(), PNG + b'external')

    # Nie nadpisuje niepowiązanego pliku ani katalogu docelowego.
    def test_occupied_target(self):
        (self.folder / 'occupied.png').mkdir()
        with self.assertRaises(ValueError):
            core.commit(self.folder, self.baseline, {'occupied.png': self.staged('new.png', PNG)})

    # Odrzuca nieudany eksport przed przeniesieniem oryginałów.
    def test_empty_export(self):
        with self.assertRaises(ValueError):
            core.commit(self.folder, self.baseline, {'c.png': self.staged('empty.png', b'')})
        self.assertEqual(core.scan(self.folder), self.baseline)

    # Odtwarza oryginalne pliki po błędzie zapisu drugiego eksportu.
    def test_rollback(self):
        original_replace = core.os.replace
        calls = [0]

        # Wywołuje jednorazowy błąd po zapisaniu pierwszego pliku.
        def fail_once(source, destination):
            calls[0] += 1
            if calls[0] == 4:
                raise OSError('simulated disk error')
            original_replace(source, destination)

        with patch.object(core.os, 'replace', fail_once), self.assertRaises(OSError):
            core.commit(self.folder, self.baseline, {
                'c.png': self.staged('c.png', PNG + b'c'),
                'd.png': self.staged('d.png', PNG + b'd')})
        self.assertEqual(core.scan(self.folder), self.baseline)

    # Nie tworzy kopii dla niezmienionych plików.
    def test_unchanged(self):
        core.commit(self.folder, self.baseline, {
            'a.png': self.staged('a.png', PNG + b'a'),
            'b.png': self.staged('b.png', PNG + b'b')})
        self.assertFalse((self.folder / '.trash').exists())


if __name__ == '__main__':
    unittest.main()