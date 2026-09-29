"""Synchronizacja katalogu PNG bez zaleznosci od GIMP."""
import hashlib
import os
from pathlib import Path
import tempfile


# Sprawdza nazwę warstwy i zwraca bezpieczną nazwę PNG także dla Windows.
def filename(name):
    if not name or name.endswith((' ', '.')) or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name):
        raise ValueError(f"Nieprawidłowa nazwa warstwy: {name!r}")
    stem = name.split('.')[0].upper()
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
    reserved.update(f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in range(1, 10))
    if stem in reserved or not stem or len(name) > 200:
        raise ValueError(f"Niedozwolona nazwa warstwy: {name!r}")
    return name if name.lower().endswith('.png') else name + '.png'


# Oblicza skrót pliku do wykrywania modyfikacji poza Gimpem.
def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


# Odczytuje wyłącznie zwykłe PNG z jednego katalogu, bez dowiązań.
def scan(folder):
    result = {}
    folded = set()
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() != '.png':
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"PNG nie jest zwykłym plikiem: {path.name}")
        filename(path.name)
        if path.name.casefold() in folded:
            raise ValueError(f"Powtórzona nazwa pliku: {path.name}")
        folded.add(path.name.casefold())
        result[path.name] = digest(path)
    return result


# Weryfikuje komplet nazw i konflikty przed wykonaniem jakiejkolwiek operacji zapisu.
def validate(folder, baseline, targets):
    folder = Path(folder)
    actual = scan(folder)
    for name, expected in baseline.items():
        if filename(name) != name or actual.get(name) != expected:
            raise ValueError(f"Plik zmieniony lub usunięty poza Gimpem: {name}")
    folded = set()
    outsiders = {path.name.casefold() for path in folder.iterdir() if path.name not in baseline}
    for name in targets:
        if filename(name) != name or name.casefold() in folded:
            raise ValueError(f"Powtórzona lub nieprawidłowa nazwa: {name}")
        if name.casefold() in outsiders:
            raise ValueError(f"Nazwa zajęta przez plik spoza dokumentu: {name}")
        folded.add(name.casefold())
    trash = folder / '.trash'
    if trash.is_symlink() or (trash.exists() and not trash.is_dir()):
        raise ValueError(".trash musi być zwykłym katalogiem.")


# Zapisuje przygotowane PNG, zachowuje kopie i odtwarza poprzedni stan przy błędzie operacji.
def commit(folder, baseline, staged):
    folder = Path(folder)
    validate(folder, baseline, staged)
    hashes = {}
    for name, path in staged.items():
        path = Path(path)
        if path.is_symlink() or path.parent.parent.resolve() != folder.resolve():
            raise ValueError("Eksport musi pochodzić z katalogu tymczasowego wewnątrz dokumentu.")
        with path.open('rb') as stream:
            if stream.read(8) != b'\x89PNG\r\n\x1a\n' or path.stat().st_size <= 8:
                raise ValueError(f"Nieprawidłowy eksport PNG: {name}")
        hashes[name] = digest(path)
    affected = [name for name in baseline if hashes.get(name) != baseline[name]]
    changed = [name for name in staged if baseline.get(name) != hashes[name]]
    if not affected and not changed:
        return hashes
    trash = folder / '.trash'
    trash.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='sync-', dir=trash))
    moved = []
    written = []
    try:
        for name in affected:
            os.replace(folder / name, backup / name)
            moved.append(name)
        for name in changed:
            destination = folder / name
            if destination.exists() or destination.is_symlink():
                raise ValueError(f"Plik pojawił się podczas zapisu: {name}")
            os.replace(staged[name], destination)
            written.append(name)
    except Exception as error:
        try:
            for name in written:
                (folder / name).unlink()
            for name in moved:
                os.replace(backup / name, folder / name)
        except Exception as rollback_error:
            raise RuntimeError(f"Błąd zapisu i odtwarzania. Kopie: {backup}; {rollback_error}") from error
        raise
    return hashes