# diff_dirs

Rekursiver Projektordner-Vergleich für Projekte ohne Git.
Vergleicht zwei Versionen eines Projekts und zeigt alle Unterschiede –
neue, gelöschte und geänderte Dateien mit zeilengenauem Diff.

---

## Wofür?

Wenn du an einem Projekt (React, Next.js, Java, …) arbeitest und **kein Git** zur Verfügung hast,
musst du Änderungen zwischen Original und angepasster Version manuell nachvollziehen.
Dieses Tool macht das automatisch: es scannt beide Ordner rekursiv, vergleicht jede Datei
per Hash und zeigt dir exakt, was sich wo geändert hat – im Terminal und optional als HTML-Report.

---

## Voraussetzungen

- **Python 3.8+**
- **PyYAML** – einmalig installieren:

```bash
pip install pyyaml
```

---

## Schnellstart

```bash
# 1. Beispiel-Config erzeugen
python diff_dirs.py --init

# 2. Config anpassen (Pfade setzen)
#    → diff_dirs.yaml öffnen und original / modified eintragen

# 3. Ausführen
python diff_dirs.py
```

Das wars. Das Script sucht automatisch nach `diff_dirs.yaml` im aktuellen Verzeichnis.

---

## Konfiguration

Alle Einstellungen stehen in einer einzigen YAML-Datei. Mit `--init` wird eine
kommentierte Vorlage erzeugt:

```yaml
# Pflichtfelder – Pfade relativ zur Config-Datei oder absolut
original: ./projekt-v1
modified: ./projekt-v2

# Ausgabe
output:
  html: true                    # HTML-Report erzeugen
  html_path: ./diff-report.html # Pfad zum Report
  color: true                   # Farbige Terminal-Ausgabe
  show_content: true            # Inhalts-Diffs anzeigen (false = nur Dateiliste)
  context_lines: 3              # Kontextzeilen um jede Änderung

# Filter
filter:
  ignore_dirs:                  # Ordner komplett ignorieren
    - node_modules
    - .next
    - dist
    - build
    - .git
    - __pycache__
    - .cache
    - target
    - .idea
    - .vscode

  ignore_files:                 # Dateimuster ignorieren (glob-Syntax)
    - "*.log"
    - ".DS_Store"
    - "Thumbs.db"
    - "*.pyc"

  # Nur bestimmte Dateitypen vergleichen (auskommentiert = alle)
  # extensions:
  #   - .ts
  #   - .tsx
  #   - .js
  #   - .java
  #   - .css
```

### Config-Referenz

| Feld | Typ | Default | Beschreibung |
|---|---|---|---|
| `original` | string | *Pflicht* | Pfad zum Original-Ordner |
| `modified` | string | *Pflicht* | Pfad zum geänderten Ordner |
| `output.html` | bool | `false` | HTML-Report erzeugen |
| `output.html_path` | string | `./diff-report.html` | Speicherort des Reports |
| `output.color` | bool | `true` | ANSI-Farben im Terminal |
| `output.show_content` | bool | `true` | Zeilengenaue Diffs anzeigen |
| `output.context_lines` | int | `3` | Kontextzeilen pro Änderung |
| `filter.ignore_dirs` | list | *siehe oben* | Ordnernamen die übersprungen werden |
| `filter.ignore_files` | list | `[]` | Glob-Patterns für Dateien |
| `filter.extensions` | list | *alle* | Whitelist für Dateiendungen |

### Pfade

Alle Pfade in der Config werden **relativ zur Config-Datei** aufgelöst.
Absolute Pfade funktionieren ebenfalls.

```yaml
# Config liegt in /home/user/configs/diff_dirs.yaml
original: ../projekte/app-v1       # → /home/user/projekte/app-v1
modified: /opt/builds/app-v2       # → /opt/builds/app-v2 (absolut)
```

---

## Verwendung

```bash
# Standard – sucht diff_dirs.yaml im aktuellen Ordner
python diff_dirs.py

# Eigene Config angeben
python diff_dirs.py mein-vergleich.yaml

# Neue Beispiel-Config erzeugen
python diff_dirs.py --init
```

### Mehrere Vergleiche

Du kannst mehrere Config-Dateien für verschiedene Vergleiche anlegen:

```bash
python diff_dirs.py frontend.yaml    # nur Frontend vergleichen
python diff_dirs.py backend.yaml     # nur Backend vergleichen
python diff_dirs.py alles.yaml       # Gesamtprojekt
```

---

## Ausgabe

### Terminal

Das Script zeigt eine farbige Zusammenfassung mit:

- Übersicht (Anzahl Dateien, Änderungen, Zeilen +/-)
- Aufschlüsselung nach Dateityp (TypeScript, Java, CSS, …)
- Liste neuer, gelöschter und binär geänderter Dateien
- Zeilengenaue Diffs für geänderte Textdateien

```
══════════════════════════════════════════════════════════════════════
  DIRECTORY DIFF REPORT
══════════════════════════════════════════════════════════════════════
  Original:  /home/user/projekt-v1
  Geändert:  /home/user/projekt-v2

  ÜBERSICHT
  Dateien im Original:    142
  Dateien in Geändert:    148
  Unverändert:            130
  + Neue Dateien:          8
  - Gelöschte Dateien:     2
  ~ Geänderte Dateien:     10
  Zeilen hinzugefügt:      +234
  Zeilen entfernt:         -87

  NACH DATEITYP
    React TSX            +3 ~5
    TypeScript           +2 ~2
    CSS                  ~3
    Java                 -2
```

### HTML-Report

Mit `output.html: true` wird ein interaktiver HTML-Report generiert:

- Dark-Theme im GitHub-Stil
- Statistik-Cards mit Übersicht
- Suchfeld zum Filtern nach Dateinamen
- Aufklappbare Diffs pro Datei
- Syntax-Highlighting für Additions/Deletions

Einfach im Browser öffnen – keine weiteren Abhängigkeiten.

---

## Typische Setups

### Next.js / React Projekt

```yaml
original: ./app-original
modified: ./app-angepasst

output:
  html: true
  html_path: ./report.html

filter:
  ignore_dirs:
    - node_modules
    - .next
    - dist
    - build
    - .git
  ignore_files:
    - "*.log"
    - "package-lock.json"
    - "yarn.lock"
```

### Java / Spring Projekt

```yaml
original: ./backend-v1
modified: ./backend-v2

output:
  html: true
  context_lines: 5

filter:
  ignore_dirs:
    - target
    - build
    - .gradle
    - .idea
    - bin
  ignore_files:
    - "*.class"
    - "*.jar"
  extensions:
    - .java
    - .xml
    - .properties
    - .yaml
```

### Nur Frontend-Code prüfen

```yaml
original: ./v1
modified: ./v2

output:
  html: false
  show_content: true
  context_lines: 5

filter:
  ignore_dirs:
    - node_modules
    - .next
  extensions:
    - .ts
    - .tsx
    - .js
    - .jsx
    - .css
    - .scss
```

### Schnellübersicht ohne Diffs

```yaml
original: ./v1
modified: ./v2

output:
  show_content: false    # nur Dateiliste, keine Inhalte
  html: false
```

---

## Erkannte Dateitypen

Das Tool erkennt und gruppiert folgende Dateitypen in der Statistik:

TypeScript, React TSX, JavaScript, React JSX, Java, Python, CSS, SCSS,
HTML, JSON, YAML, XML, Markdown, SQL, Shell, Environment, Properties,
Gradle, TOML, Config. Andere Dateitypen werden anhand ihrer Endung angezeigt.

Binärdateien (Bilder, Fonts, Archive, etc.) werden per Hash verglichen
und als „binär geändert" gemeldet – ohne Inhalts-Diff.

---

## Projektstruktur

```
diff_dirs.py        # Das Script
diff_dirs.yaml      # Deine Konfiguration (wird mit --init erzeugt)
diff-report.html    # HTML-Report (wird bei html: true erzeugt)
README.md           # Diese Datei
```
