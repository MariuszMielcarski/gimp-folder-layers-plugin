# Folder Layers dla GIMP 3

## O pluginie

Folder Layers sprawia, że zwykły katalog z plikami PNG może służyć jako edytowalny dokument warstwowy w Gimpie 3. Otwiera PNG jako osobne, nazwane warstwy jednego obrazu, a następnie synchronizuje zmiany struktury obrazu i zapis warstw z powrotem do katalogu. Celem jest edycja zestawów sprite'ów, elementów postaci lub klatek animacji bezpośrednio w Gimpie, przy zachowaniu zwykłych PNG jako plików wynikowych dla gry albo innego narzędzia.

Plugin nie jest importerem ani edytorem SVG/ORA i nie zastępuje formatu projektu Gimpa. Dokumentem roboczym nadal może być XCF; katalog PNG jest zsynchronizowanym zestawem wejściowych i wyjściowych warstw. Nie ma zależności od Boa, jej API ani formatu konkretnych sprite'ów, więc plugin może później zostać wydzielony do osobnego repozytorium.

### Model synchronizacji

- Przy otwarciu katalogu plugin skanuje zwykłe pliki PNG w tym jednym katalogu i tworzy obraz GIMP o wymiarach pierwszego pliku. Każda warstwa dostaje trwały identyfikator zapisany jako parasite GIMP; mapowanie nie opiera się wyłącznie na nazwie, bo nazwa może się zmienić albo warstwę można zduplikować.
- Niemodalne okno monitora co sekundę porównuje strukturę warstw z poprzednim stanem. Zmiana nazwy zmienia nazwę przypisanego pliku, dodanie warstwy tworzy PNG, a usunięcie warstwy przenosi powiązany PNG do `.trash`. Zmiany struktury są więc synchronizowane automatycznie, ale tylko gdy monitor pozostaje otwarty.
- Zmiany pikseli nie są stale obserwowane. Przycisk **Zapisz wszystkie PNG** eksportuje każdą warstwę osobno. Synchronizacja struktury także eksportuje bieżące piksele wszystkich warstw, żeby zmiana nazwy lub usunięcie nie zapisały przypadkiem tylko części obrazu.
- Eksport pojedynczej warstwy odbywa się w tymczasowym obrazie o wymiarach całego płótna, a następnie trafia do transakcyjnego rdzenia plikowego. Dzięki temu zachowuje rozmiar i offset w obrębie wspólnego płótna oraz przezroczyste marginesy. Warstwa jest eksportowana niezależnie od widoczności.
- XCF zachowuje metadane powiązania obrazu z katalogiem. Standardowe **Ctrl+S** nadal zapisuje XCF, a nie pliki PNG. Po ponownym otwarciu XCF należy ponownie uruchomić monitor/synchronizację.

### Granice i bezpieczeństwo

Synchronizacja plików nie jest częścią historii Undo Gimpa. Usunięte i zastępowane pliki są dlatego zachowywane w `.trash`. Skróty SHA-256 wykrywają zmianę pliku poza Gimpem; konflikt ma zatrzymać zapis zamiast bez pytania nadpisać zewnętrzną pracę. Nowe pliki dodane do katalogu po otwarciu nie są importowane automatycznie, a niepowiązane pliki nie są usuwane.

To prototyp dla płaskich warstw PNG o jednakowych wymiarach. Nie obsługuje grup warstw, trybów mieszania zależnych od innych warstw ani warstw wychodzących poza płótno. Nie zapisuje do katalogu kolejności i widoczności; te właściwości należą do XCF. Monitor odpytuje obraz co sekundę, nie subskrybuje zdarzeń edytora; nie należy otwierać dwóch monitorów dla tego samego obrazu.

Logika transakcji, walidacji nazw, porównywania skrótów oraz kopii zapasowych jest oddzielona w `folder-layers/folder_layers_core.py` i testowana bez GIMP-a. `folder-layers/folder-layers.py` zawiera adapter API GIMP/GI i interfejs. Ta granica pozwala przenosić oraz testować bezpieczeństwo operacji na plikach niezależnie od wersji API Gimpa.

## Instalacja

### Windows: skrypt instalacyjny

Zamknij Gimpa i uruchom z katalogu repozytorium:

```powershell
.\gimp\install.ps1
```

[install.ps1](install.ps1) kopiuje tylko dwa pliki Python do katalogu pluginów najwyższej znalezionej wersji Gimpa, na przykład `%APPDATA%\GIMP\3.2\plug-ins\folder-layers`. Nie wymaga administratora ani osobnej instalacji Pythona. Ponowne uruchomienie pomija identyczne pliki; nadpisanie różniącej się wersji wymaga `-Force`. Inne pliki pozostają nietknięte.

```powershell
.\gimp\install.ps1 -Force
.\gimp\install.ps1 -PluginDirectory "D:\GIMP\plug-ins"
.\gimp\install.ps1 -WhatIf
```

`-PluginDirectory` wskazuje katalog **Wtyczki**, nie podkatalog `folder-layers`. `-WhatIf` pokazuje plan instalacji bez kopiowania plików. Jeśli PowerShell blokuje lokalny skrypt, możesz zezwolić na jego wykonanie wyłącznie w bieżącej sesji poleceniem `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

Po instalacji uruchom ponownie Gimpa.

### Instalacja ręczna

1. W Gimpie otwórz **Edycja → Preferencje → Foldery → Wtyczki** i sprawdź ścieżkę użytkownika.
2. Skopiuj tylko katalog [folder-layers](folder-layers) wraz z oboma plikami Python do tego katalogu wtyczek. Typowa ścieżka Windows to `%APPDATA%\GIMP\3.2\plug-ins\folder-layers\folder-layers.py`.
3. Uruchom ponownie Gimpa. W menu **Plik** znajdziesz **Otwórz katalog jako warstwy...** oraz **Synchronizuj katalog warstw...**. Można je też znaleźć wyszukiwarką akcji Gimpa.

Wtyczka korzysta z Pythona i bibliotek GI dostarczonych z Gimpem. Nie wymaga instalowania Pillow, pip ani bibliotek gry. Na Linuxie plik `folder-layers.py` musi mieć prawo wykonywania.

## Praca

- Najpierw wypróbuj na kopii katalogu. Wybierz katalog z PNG o jednakowych wymiarach. Pliki ładowane są alfabetycznie, pierwszy jest górną warstwą.
- Pozostaw okno monitora otwarte i edytuj obraz w głównym oknie Gimpa.
- Monitor co sekundę wykrywa nowe, usunięte i przemianowane warstwy. Synchronizuje pliki automatycznie; nazwa warstwy staje się nazwą pliku, z automatycznym dopisaniem `.png`.
- **Zapisz wszystkie PNG** zapisuje aktualne piksele wszystkich warstw. Zmiana samego rysunku nie uruchamia automatycznego zapisu. Automatyczna synchronizacja struktury zapisuje również bieżące piksele pozostałych warstw.
- **Ctrl+S nadal zapisuje dokument Gimpa, nie katalog PNG.** Możesz zapisać dodatkowo XCF: zachowa powiązanie katalogu i identyfikatory. Po ponownym otwarciu XCF uruchom **Synchronizuj katalog warstw...**.
- Zamknięcie monitora zatrzymuje synchronizację, nie zapisuje niezatwierdzonych pikseli. Przycisk zapisu należy użyć przed zamknięciem.

## Bezpieczeństwo

- Usunięte i zastąpione pliki trafiają do `.trash/sync-...` wewnątrz katalogu. Nie są kasowane bezpowrotnie. Folder kopii trzeba okresowo sprzątać samodzielnie.
- Nazwy muszą być unikalne także bez rozróżniania wielkości liter i poprawne w Windows. Nieprawidłowa nazwa zatrzymuje automat.
- Zmiana lub usunięcie powiązanego PNG poza Gimpem blokuje zapis. Otwórz katalog ponownie, by przyjąć nową wersję dyskową. Nowe pliki z dysku nie są automatycznie importowane i nie są usuwane przez synchronizację.
- Eksporty powstają w katalogu tymczasowym. Przy błędzie operacji plikowych wtyczka próbuje odtworzyć poprzednią zawartość; błędu odzyskiwania nie ukrywa. Nie gwarantuje transakcyjności przy awarii procesu/systemu ani ochrony przed równoczesnym zapisem przez drugi program w tej samej chwili.
- Cofanie w Gimpie nie cofa bezpośrednio dysku. Przy działającym monitorze przywrócenie struktury jest kolejną synchronizacją. Zmiany samych pikseli wymagają ponownego zapisu.

## Zakres prototypu

Płaskie warstwy, PNG RGB/RGBA, przezroczyste marginesy i przesunięcia wewnątrz wspólnego płótna. Ukryta warstwa też jest eksportowana. Grupy i warstwy wychodzące poza płótno są odrzucane. Każda warstwa jest renderowana osobno: tryby mieszania zależne od warstw poniżej nie zachowają wyniku całej kompozycji. Kolejność i widoczność warstw nie są zapisywane do katalogu; zachowuje je XCF.

Monitor działa tylko przez czas otwarcia jego okna. Nie uruchamiaj dwóch monitorów dla tego samego dokumentu. Pierwsza wersja nie zastępuje natywnego formatu XCF ani standardowych poleceń zapisu.

## Testy

Z katalogu repo:

```powershell
python -m unittest discover -s gimp/tests -p test_core.py
python gimp/tests/run_gimp_test.py --gimp "C:\ścieżka\do\gimp-console-3.2.exe"
```

Testy operacji na plikach nie wymagają Gimpa. Test integracyjny korzysta wyłącznie z katalogu tymczasowego; nie dotyka PNG gry ani dokumentów użytkownika.

Sprawdzone lokalnie: 8 testów rdzenia oraz test importu, eksportu ukrytej warstwy, metadanych, zmiany nazwy, usunięcia, kopii zapasowych i duplikowania na GIMP 3.2.4. Interaktywne menu i monitor wymagają jeszcze próby po instalacji; nie były testowane przez klikanie w interfejsie. Starszy GIMP 3.0 nie był uruchamiany w testach.
