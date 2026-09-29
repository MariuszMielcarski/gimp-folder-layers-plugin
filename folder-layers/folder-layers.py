#!/usr/bin/env python3
"""GIMP 3: katalog PNG jako dokument warstwowy."""
import json
from pathlib import Path
import sys
import tempfile
import uuid

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gimp, GimpUi, Gtk, Gio, GLib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import folder_layers_core as core

DOCUMENT_KEY = 'folder-layers-document-v1'
LAYER_KEY = 'folder-layers-id-v1'


# Zapisuje trwałe metadane JSON w obrazie lub warstwie, również przy zapisie XCF.
def put_metadata(item, key, value):
    data = json.dumps(value, ensure_ascii=True).encode('utf-8')
    if not item.attach_parasite(Gimp.Parasite.new(key, 1, data)):
        raise RuntimeError("Nie można zapisać powiązania z katalogiem.")


# Odczytuje metadane dokumentu lub warstwy.
def get_metadata(item, key):
    parasite = item.get_parasite(key)
    return json.loads(bytes(parasite.get_data()).decode('utf-8')) if parasite else None


# Otwiera PNG jako warstwy o wspólnych wymiarach i zapamiętuje ich oryginalne pliki.
def open_folder(folder):
    folder = Path(folder).resolve()
    baseline = core.scan(folder)
    if not baseline:
        raise ValueError("Katalog nie zawiera plików PNG.")
    names = list(baseline)
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(str(folder / names[0])))
    if image is None:
        raise RuntimeError("Nie udało się otworzyć pierwszego PNG.")
    try:
        first_layer = image.get_layers()[0]
        mapping = {}
        for index, name in enumerate(names):
            layer = first_layer if index == 0 else Gimp.file_load_layer(
                Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(str(folder / name)))
            if layer is None:
                raise RuntimeError(f"Nie można otworzyć: {name}")
            if layer.get_width() != image.get_width() or layer.get_height() != image.get_height():
                raise ValueError("W pierwszej wersji wszystkie PNG muszą mieć jednakowe wymiary.")
            if index:
                image.insert_layer(layer, None, index)
            layer.set_offsets(0, 0)
            layer.set_name(name)
            identity = uuid.uuid4().hex
            put_metadata(layer, LAYER_KEY, identity)
            mapping[identity] = name
        core.validate(folder, baseline, names)
        put_metadata(image, DOCUMENT_KEY, {'folder': str(folder), 'baseline': baseline, 'mapping': mapping})
        return image
    except Exception:
        image.delete()
        raise


# Pobiera stabilne identyfikatory i nazwy; odrzuca grupy i warstwy poza płótnem.
def snapshot(image):
    result = []
    identities = set()
    names = set()
    for layer in image.get_layers():
        if layer.is_group():
            raise ValueError("Grupy warstw nie są obsługiwane; użyj płaskich warstw PNG.")
        success, offset_x, offset_y = layer.get_offsets()
        if not success:
            raise ValueError("Nie można odczytać przesunięcia warstwy.")
        if offset_x < 0 or offset_y < 0 or offset_x + layer.get_width() > image.get_width() or offset_y + layer.get_height() > image.get_height():
            raise ValueError("Warstwa wystaje poza płótno. Powiększ płótno przed zapisem.")
        identity = get_metadata(layer, LAYER_KEY)
        if not identity or identity in identities:
            identity = uuid.uuid4().hex
            put_metadata(layer, LAYER_KEY, identity)
        name = core.filename(layer.get_name())
        if name.casefold() in names:
            raise ValueError(f"Dwie warstwy mają tę samą nazwę: {name}")
        names.add(name.casefold())
        identities.add(identity)
        result.append((identity, name, layer))
    return result


# Eksportuje pojedynczą warstwę na przezroczystym płótnie bez pozostałych warstw.
def export_layer(image, layer, destination):
    temporary = Gimp.Image.new(image.get_width(), image.get_height(), Gimp.ImageBaseType.RGB)
    try:
        copied = Gimp.Layer.new_from_drawable(layer, temporary)
        temporary.insert_layer(copied, None, 0)
        copied.set_visible(True)
        procedure = Gimp.get_pdb().lookup_procedure('file-png-export')
        config = procedure.create_config()
        config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
        config.set_property('image', temporary)
        config.set_property('file', Gio.File.new_for_path(str(destination)))
        for name in ('include-exif', 'include-iptc', 'include-xmp', 'include-thumbnail', 'include-comment', 'time', 'offs'):
            if config.find_property(name):
                config.set_property(name, False)
        result = procedure.run(config)
        if result.index(0) != Gimp.PDBStatusType.SUCCESS:
            raise RuntimeError(f"Eksport PNG nie powiódł się: {destination.name}")
    finally:
        temporary.delete()


# Zapisuje wszystkie warstwy transakcyjnie i aktualizuje powiązanie dokumentu z dyskiem.
def sync_image(image):
    document = get_metadata(image, DOCUMENT_KEY)
    if not document:
        raise ValueError("Ten obraz nie został otwarty jako katalog warstw.")
    layers = snapshot(image)
    targets = [name for identity, name, layer in layers]
    core.validate(document['folder'], document['baseline'], targets)
    with tempfile.TemporaryDirectory(prefix='.folder-layers-', dir=document['folder']) as directory:
        staged = {}
        for index, (identity, name, layer) in enumerate(layers):
            destination = Path(directory) / f'{index}.png'
            export_layer(image, layer, destination)
            staged[name] = destination
        document['baseline'] = core.commit(document['folder'], document['baseline'], staged)
    document['mapping'] = {identity: name for identity, name, layer in layers}
    put_metadata(image, DOCUMENT_KEY, document)
    Gimp.displays_flush()


class FolderLayersPlugin(Gimp.PlugIn):
    # Wyłącza domyślną domenę tłumaczeń dla samodzielnego pluginu.
    def do_set_i18n(self, procedure_name):
        return False, None, None

    # Udostępnia polecenia otwarcia katalogu oraz ponownego uruchomienia synchronizacji.
    def do_query_procedures(self):
        return ['python-fu-folder-layers-open', 'python-fu-folder-layers-monitor']

    # Rejestruje polecenia dla GIMP 3 w menu Plik.
    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run)
        procedure.set_image_types('*')
        if name.endswith('-open'):
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_menu_label('Otwórz katalog jako warstwy...' if name.endswith('-open') else 'Synchronizuj katalog warstw...')
        procedure.add_menu_path('<Image>/File')
        procedure.set_documentation('Katalog PNG jako warstwy', 'Otwiera katalog PNG lub uruchamia monitor zmian i zapis warstw.', name)
        return procedure

    # Uruchamia interaktywny wybór katalogu lub monitor dla bieżącego obrazu.
    def run(self, procedure, run_mode, image, drawables, config, *unused):
        if run_mode != Gimp.RunMode.INTERACTIVE:
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error('Polecenie wymaga interfejsu Gimpa.'))
        GimpUi.init('folder-layers')
        try:
            if procedure.get_name().endswith('-open'):
                chooser = Gtk.FileChooserDialog(title='Otwórz katalog PNG jako warstwy', action=Gtk.FileChooserAction.SELECT_FOLDER)
                chooser.add_buttons('Anuluj', Gtk.ResponseType.CANCEL, 'Otwórz', Gtk.ResponseType.OK)
                response = chooser.run()
                folder = chooser.get_filename()
                chooser.destroy()
                if response != Gtk.ResponseType.OK:
                    return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)
                image = open_folder(folder)
                Gimp.Display.new(image)
            if image is None or not get_metadata(image, DOCUMENT_KEY):
                raise ValueError('Wybierz dokument otwarty z katalogu PNG.')
            self.monitor(image)
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)
        except Exception as error:
            Gimp.message(str(error))
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(error)))

    # Pozostawia niemodalne okno z automatyczną synchronizacją struktury i ręcznym zapisem pikseli.
    def monitor(self, image):
        dialog = Gtk.Dialog(title='Katalog warstw', modal=False)
        dialog.add_button('Zapisz wszystkie PNG', Gtk.ResponseType.APPLY)
        dialog.add_button('Zamknij monitor', Gtk.ResponseType.CLOSE)
        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_border_width(16)
        document = get_metadata(image, DOCUMENT_KEY)
        label = Gtk.Label(label=document['folder'])
        content.add(label)
        automatic = Gtk.CheckButton(label='Synchronizuj nazwy, dodawanie i usuwanie co sekundę')
        automatic.set_active(True)
        content.add(automatic)
        status = Gtk.Label(label='Kopie i usunięte pliki: .trash. Piksele zapisuje przycisk powyżej.')
        status.set_line_wrap(True)
        content.add(status)
        saved_structure = [tuple(sorted(document['mapping'].items()))]

        # Zapisuje bieżący dokument i wstrzymuje automat przy konflikcie lub błędzie eksportu.
        def save():
            try:
                sync_image(image)
                saved_structure[0] = tuple(sorted((identity, name) for identity, name, layer in snapshot(image)))
                status.set_text('Zapisano PNG. Poprzednie wersje: .trash.')
            except Exception as error:
                automatic.set_active(False)
                status.set_text(f'Wstrzymano: {error}')

        # Sprawdza strukturę obrazu bez automatycznego zapisu każdego pociągnięcia pędzla.
        def tick():
            if not image.is_valid():
                dialog.destroy()
                return False
            if automatic.get_active():
                try:
                    current = tuple(sorted((identity, name) for identity, name, layer in snapshot(image)))
                    if current != saved_structure[0]:
                        save()
                except Exception as error:
                    automatic.set_active(False)
                    status.set_text(f'Wstrzymano: {error}')
            return True

        # Obsługuje przyciski zapisu i zamknięcia bez blokowania edycji obrazu.
        def respond(widget, response):
            if response == Gtk.ResponseType.APPLY:
                save()
            else:
                dialog.destroy()

        # Kończy lokalną pętlę interfejsu po zamknięciu monitora.
        def close(widget):
            loop.quit()

        loop = GLib.MainLoop()
        dialog.connect('response', respond)
        dialog.connect('destroy', close)
        timer = GLib.timeout_add(1000, tick)
        dialog.show_all()
        loop.run()
        if GLib.MainContext.default().find_source_by_id(timer):
            GLib.source_remove(timer)


if __name__ == '__main__':
    Gimp.main(FolderLayersPlugin.__gtype__, sys.argv)