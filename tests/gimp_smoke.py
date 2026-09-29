"""Test integracyjny uruchamiany przez python-fu-eval, wyłącznie na danych tymczasowych."""
import importlib.util
from pathlib import Path
import tempfile

plugin_path = Path('gimp/folder-layers/folder-layers.py').resolve()
specification = importlib.util.spec_from_file_location('folder_plugin', plugin_path)
plugin = importlib.util.module_from_spec(specification)
specification.loader.exec_module(plugin)
from gi.repository import Gimp, Gio

with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    seed = Gimp.Image.new(19, 19, Gimp.ImageBaseType.RGB)
    layer = Gimp.Layer.new(seed, 'seed', 19, 19, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    seed.insert_layer(layer, None, 0)
    layer.fill(Gimp.FillType.WHITE)
    plugin.export_layer(seed, layer, folder / 'a.png')
    plugin.export_layer(seed, layer, folder / 'b.png')
    seed.delete()
    image = plugin.open_folder(folder)
    assert len(image.get_layers()) == 2
    top, bottom = image.get_layers()
    top.set_name('renamed')
    top.set_visible(False)
    image.remove_layer(bottom)
    plugin.sync_image(image)
    assert (folder / 'renamed.png').is_file()
    assert not (folder / 'a.png').exists()
    assert not (folder / 'b.png').exists()
    assert len(list((folder / '.trash').glob('*/*.png'))) == 2
    loaded = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(str(folder / 'renamed.png')))
    assert loaded.get_width() == 19 and loaded.get_height() == 19
    loaded.delete()
    duplicated = top.copy()
    image.insert_layer(duplicated, None, 0)
    duplicated.set_name('extra')
    plugin.sync_image(image)
    assert (folder / 'extra.png').is_file()
    assert plugin.get_metadata(top, plugin.LAYER_KEY) != plugin.get_metadata(duplicated, plugin.LAYER_KEY)
    image.delete()
print('PASS GIMP integration: load, metadata, hidden export, rename, delete, backups, duplication')