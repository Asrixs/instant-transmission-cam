# Instant Transmission Cam

Verdwijn uit je webcambeeld door wijs- en middelvinger tegen je voorhoofd te
zetten, zoals Goku's *Instant Transmission*. Werkt in elke app of website die
je camera gebruikt (Teams, Zoom, Google Meet, Discord, ...) via een virtuele
camera.

```
Echte webcam → Instant Transmission Cam → OBS Virtual Camera → Teams / Zoom / Meet
                (gebaar herkennen + effect)
```

Alles draait lokaal op je computer. Er wordt niets opgenomen of verstuurd.

**Status:** fase 3: met het gebaar verdwijn je uit beeld en kom je weer
terug, met een zachte overgang. Het spectaculaire teleport-effect volgt in
fase 4 (zie [Planning](#planning)).

## Wat heb je nodig

- Windows 11
- [Python](https://www.python.org/downloads/) **3.11 t/m 3.14**, bij voorkeur 3.13 (zie hieronder)
- [OBS Studio](https://obsproject.com/) 28 of nieuwer (levert de virtuele camera)
- Git
- Een webcam

### Python-versie

Nieuwere versies (3.15 en hoger) werken nog niet: `pyvirtualcam`, de
koppeling met de virtuele camera, is daar nog niet voor beschikbaar. Je kunt
Python 3.13 gewoon **naast** een nieuwere versie installeren; `start.bat` kiest
zelf de juiste.

Controleer welke versies je hebt met `py --list` in PowerShell. Staat 3.13 (of
3.11, 3.12, 3.14) er niet tussen, installeer hem dan met:

```powershell
py install 3.13
```

Herkent PowerShell `py install` niet, download dan het Python 3.13-installatieprogramma
("Windows installer (64-bit)") via [python.org/downloads/windows](https://www.python.org/downloads/windows/).

## Eenmalig: OBS instellen

OBS hoeft straks niet open te staan; we gebruiken alleen de virtuele camera
die OBS bij Windows registreert. Zekerheidshalve één keer:

1. Open OBS Studio (de installatiewizard mag je overslaan).
2. Klik rechtsonder bij **Bediening** op **Virtuele camera starten**.
3. Klik op **Virtuele camera stoppen** en sluit OBS.

> Staat de virtuele camera in OBS zelf aan, dan kan dit programma hem niet
> gebruiken. Laat hem in OBS dus altijd uit.

## Installeren

Open een terminal (PowerShell) in de map waar je het project wilt hebben:

```powershell
git clone https://github.com/Asrixs/instant-transmission-cam.git
cd instant-transmission-cam
.\start.bat
```

Of dubbelklik daarna gewoon op `start.bat` in Verkenner. De eerste keer duurt
het een paar minuten: er wordt een Python-omgeving gemaakt (`.venv`) en de
onderdelen en herkenningsmodellen worden gedownload. Daarna start het meteen.

Bijwerken naar een nieuwe versie: `git pull` en opnieuw `start.bat`.

## Gebruiken in een vergadering

1. **Start eerst `start.bat`.** Er opent een voorbeeldvenster en de terminal
   meldt `Virtuele camera actief: OBS Virtual Camera`.
2. **Kies in je vergaderapp de camera "OBS Virtual Camera":**
   - Teams: Instellingen → Apparaten → Camera
   - Zoom: Instellingen → Video → Camera
   - Google Meet (browser): tandwiel → Video → Camera. Herlaad de pagina als
     de camera er nog niet tussen staat.
3. Je webcam kan maar door één programma tegelijk gebruikt worden. Kies in de
   vergaderapp dus nooit je echte webcam, anders kan dit programma er niet bij.

Het voorbeeldvenster toont wat de anderen zien, plus hulplijnen en tekst. Die
hulplijnen en tekst komen **niet** in de virtuele camera.

## De lege kamer vastleggen

Om te kunnen verdwijnen moet het programma weten hoe de kamer eruitziet
zonder jou:

1. Bij het starten telt het voorbeeldvenster af: **Stap uit beeld: 4, 3, 2, 1**.
2. Stap helemaal uit beeld, ook met je handen en schouders.
3. Ben je nog (deels) in beeld, dan wacht het programma en meldt het
   *Je bent nog in beeld - stap opzij*. Na 10 seconden wachten legt het de
   kamer toch vast, voor het geval een poster of tv voor een persoon wordt
   aangezien.
4. Bij *Lege kamer vastgelegd!* kun je terugkomen.

Druk op **spatie** om de lege kamer opnieuw vast te leggen, bijvoorbeeld als
je de camera hebt verschoven of het licht flink is veranderd.

**Tips voor het beste resultaat**
- Zet je camera stevig neer; als hij beweegt klopt de foto van de kamer niet meer.
- Kleine lichtverschillen (de camera die zijn belichting aanpast) worden
  automatisch gecorrigeerd. Doe je een lamp aan of uit, druk dan op spatie.
- Wat er achter je beweegt (een huisdier, iemand die langsloopt) blijft
  gewoon zichtbaar: alleen jij wordt vervangen.

## Het gebaar

1. Strek wijs- en middelvinger en houd ze **tegen elkaar** (geen V-teken).
2. Vouw ring- en pink in; je duim maakt niet uit.
3. Zet de vingertoppen **midden op je voorhoofd**.
4. Houd dat **1 seconde** vast. De groene ring rond je voorhoofd loopt vol.

Bij herkenning knippert de rand van het voorbeeldvenster groen en **verdwijn
je**. Doe het gebaar nog een keer om terug te komen; haal je hand daarvoor
eerst even weg.

Terwijl je onzichtbaar bent, toont het voorbeeldvenster rechtsboven een klein
live beeld van jezelf (*jij (alleen hier)*), zodat je ziet wat je doet. De
anderen zien dat niet.

## Toetsen (in het voorbeeldvenster)

| Toets | Actie |
|---|---|
| `Spatie` | Lege kamer opnieuw vastleggen |
| `V` | Verdwijnen/verschijnen zonder gebaar (handig om te testen) |
| `Q` / `Esc` | Stoppen |
| `H` | Hulplijnen en tekst aan/uit |
| `M` | Voorbeeld spiegelen aan/uit (de virtuele camera wordt nooit gespiegeld) |

## Opties

Opties zet je achter `start.bat`, bijvoorbeeld `.\start.bat --camera 1 --debug`.

| Optie | Betekenis |
|---|---|
| `--camera 1` | Andere webcam gebruiken (standaard `0`) |
| `--width 1920 --height 1080` | Resolutie (standaard 1280x720) |
| `--hold 0.8` | Hoe lang je het gebaar moet vasthouden, in seconden |
| `--countdown 6` | Seconden om uit beeld te stappen bij het vastleggen van de lege kamer (standaard 4) |
| `--transition 1` | Duur van verdwijnen en verschijnen, in seconden (standaard 0.5) |
| `--debug` | Meetwaarden van het gebaar in de terminal tonen |
| `--no-virtual-camera` | Alleen het voorbeeldvenster, zonder virtuele camera |
| `--virtual-camera` | Stoppen met een foutmelding als de virtuele camera niet werkt |

## Wordt het gebaar niet (goed) herkend?

Het voorbeeldvenster toont onder **Mist nog** wat er aan het gebaar ontbreekt,
bijvoorbeeld `middelvinger niet gestrekt`. Houd je hand iets meer naar de
camera gedraaid als de middelvinger achter je wijsvinger verdwijnt; dan kan
de camera beide vingers zien.

Voor de precieze meetwaarden start je met `.\start.bat --debug`, maak je het
gebaar en kopieer je een paar `[Debug]`-regels. Zo lees je ze:

| Waarde | Moet zijn | Betekenis |
|---|---|---|
| `wijs`, `midden` | ≥ 1.10 | Vinger gestrekt |
| `ring`, `pink` | ≤ 1.15 | Vinger ingevouwen |
| | verschil ≥ 0.10 | Gestrekte vingers duidelijk langer dan ingevouwen |
| `tussenruimte` | ≤ 0.55 | Vingertoppen tegen elkaar |
| `voorhoofd` | ≤ 0.60 | Vingertoppen dicht bij het voorhoofd |

Valt de herkenning heel even weg (korter dan 0,4 seconde), dan loopt de teller
gewoon door.

De regels die beginnen met `W0000` of `INFO` komen van MediaPipe zelf en zijn
onschuldig.

De grenzen staan in `itcam/gesture.py` (`GestureSettings`).

## Problemen oplossen

| Melding of probleem | Oplossing |
|---|---|
| `Virtuele camera niet beschikbaar` | Controleer of OBS Studio is geïnstalleerd en de virtuele camera in OBS uit staat. Doe de stappen bij [OBS instellen](#eenmalig-obs-instellen) nog eens. |
| `Webcam 0 is niet beschikbaar` | Sluit Teams/Zoom/browsertabbladen die de camera gebruiken, of probeer `--camera 1`. |
| Vergaderapp toont zwart beeld of het OBS-logo | Draait `start.bat` nog? Kies daarna opnieuw "OBS Virtual Camera" in de app. |
| `Geen geschikte Python-versie gevonden` of `No matching distribution found for pyvirtualcam` | Je hebt een te nieuwe Python-versie. Installeer Python 3.13 ernaast, zie [Python-versie](#python-versie). `start.bat` maakt de omgeving dan vanzelf opnieuw aan. |
| Er blijft een "spook" of rand van je zichtbaar | Druk op spatie en leg de lege kamer opnieuw vast; zorg dat je dan echt helemaal uit beeld bent. |
| Een stuk van de kamer "bevriest" | Dat deel wijkt af van de vastgelegde foto (licht veranderd, iets verplaatst). Druk op spatie. |
| Het beeld hapert als je onzichtbaar bent | Probeer een lagere resolutie: `--width 960 --height 540`. |
| Installatie mislukt halverwege | Verwijder de map `.venv` en start `start.bat` opnieuw. |

## Planning

1. ✅ Webcambeeld doorgeven aan de virtuele camera
2. ✅ Instant Transmission-gebaar herkennen
3. ✅ Verdwijnen en terugkomen: lege kamer vastleggen en jezelf eruit knippen
4. ⬜ Teleport-effect
5. ⬜ Geluid, instellingen en een los te starten programma

## Voor ontwikkelaars

```
itcam/
  app.py        hoofdlus: webcam → herkenning → verdwijnen → virtuele camera + voorbeeld
  camera.py     webcam openen en OBS Virtual Camera aansturen
  detector.py   MediaPipe: voorhoofd (Face Landmarker) en handen (Hand Landmarker)
  gesture.py    rekenwerk voor het gebaar en de houdtijd, zonder camera testbaar
  segmenter.py  MediaPipe: welke pixels bij jou horen (Selfie Segmenter)
  vanish.py     lege kamer vastleggen, masker, helderheid en overgang, zonder camera testbaar
  models.py     eenmalige download van de MediaPipe-modellen naar models/
tests/          tests voor gesture.py en vanish.py
```

Hoe het verdwijnen werkt: het masker van de Selfie Segmenter wordt
gecombineerd met alles wat afwijkt van de vastgelegde lege kamer (dat vangt
bijvoorbeeld kleding in de kleur van de muur). Het masker wordt iets vergroot
en zacht gemaakt, en op die plek komt de lege kamer, aangepast aan de huidige
belichting van de camera.

```
```

Tests draaien:

```powershell
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest
```
