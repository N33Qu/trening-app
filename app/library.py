"""Exercise library: curated catalogue from Free Exercise DB (public domain).

Metadata (names, muscles, equipment, instructions in PL and EN, photo paths)
is read from app/data/exercises.json, built by scripts/import_exercises.py.
The database only stores the slug that links a catalogue exercise to its entry.
"""

import json
from functools import cache
from pathlib import Path

from flask_babel import lazy_gettext

from .i18n import current_language

DATA_FILE = Path(__file__).resolve().parent / "data" / "exercises.json"

MUSCLE_LABELS = {
    "abdominals": lazy_gettext("brzuch"),
    "abductors": lazy_gettext("odwodziciele ud"),
    "adductors": lazy_gettext("przywodziciele ud"),
    "biceps": lazy_gettext("biceps"),
    "calves": lazy_gettext("łydki"),
    "chest": lazy_gettext("klatka piersiowa"),
    "forearms": lazy_gettext("przedramiona"),
    "glutes": lazy_gettext("pośladki"),
    "hamstrings": lazy_gettext("dwugłowe uda"),
    "lats": lazy_gettext("najszersze grzbietu"),
    "lower back": lazy_gettext("dolna część pleców"),
    "middle back": lazy_gettext("środek pleców"),
    "neck": lazy_gettext("szyja"),
    "quadriceps": lazy_gettext("czworogłowe uda"),
    "shoulders": lazy_gettext("barki"),
    "traps": lazy_gettext("czworoboczne (kaptury)"),
    "triceps": lazy_gettext("triceps"),
}
EQUIPMENT_LABELS = {
    "barbell": lazy_gettext("sztanga"),
    "e-z curl bar": lazy_gettext("sztanga łamana"),
    "dumbbell": lazy_gettext("hantle"),
    "kettlebells": lazy_gettext("kettlebell"),
    "cable": lazy_gettext("wyciąg"),
    "machine": lazy_gettext("maszyna"),
    "body only": lazy_gettext("masa ciała"),
    "bands": lazy_gettext("gumy oporowe"),
    "medicine ball": lazy_gettext("piłka lekarska"),
    "exercise ball": lazy_gettext("piłka gimnastyczna"),
    "foam roll": lazy_gettext("wałek do rolowania"),
    "other": lazy_gettext("inne"),
}
LEVEL_LABELS = {
    "beginner": lazy_gettext("początkujący"),
    "intermediate": lazy_gettext("średniozaawansowany"),
    "expert": lazy_gettext("zaawansowany"),
}
FORCE_LABELS = {
    "push": lazy_gettext("wypychanie"),
    "pull": lazy_gettext("przyciąganie"),
    "static": lazy_gettext("statyczne"),
}
MECHANIC_LABELS = {
    "compound": lazy_gettext("wielostawowe"),
    "isolation": lazy_gettext("izolowane"),
}
KIND_LABELS = {
    "strength": lazy_gettext("siłowe"),
    "powerlifting": lazy_gettext("trójbój siłowy"),
    "olympic weightlifting": lazy_gettext("podnoszenie ciężarów"),
    "strongman": lazy_gettext("strongman"),
    "plyometrics": lazy_gettext("plyometria"),
    "cardio": lazy_gettext("cardio"),
    "stretching": lazy_gettext("rozciąganie"),
}
# Order used for grouping in the workout form and in the muscle filter.
MUSCLE_ORDER = ["chest", "lats", "middle back", "lower back", "traps", "shoulders", "biceps", "triceps",
                "forearms", "abdominals", "quadriceps", "hamstrings", "glutes", "adductors", "abductors",
                "calves", "neck"]


class LibraryEntry:
    """Read-only view of one catalogue entry, localised to the active language."""

    def __init__(self, data):
        self.data = data
        self.slug = data["slug"]

    def _lang(self, field):
        lang = current_language()
        return self.data.get(f"{field}_{lang}") or self.data[f"{field}_en"]

    @property
    def name(self):
        return self._lang("name")

    @property
    def instructions(self):
        return self._lang("instructions")

    @property
    def primary(self):
        return self.data["primary"]

    @property
    def secondary(self):
        return self.data["secondary"]

    @property
    def images(self):
        return self.data["images"]

    @property
    def thumbnail(self):
        return self.images[0] if self.images else None

    @property
    def equipment(self):
        return self.data["equipment"]

    @property
    def level(self):
        return self.data["level"]

    @property
    def search_text(self):
        d = self.data
        return " ".join([d["name_pl"], d["name_en"], d["slug"]]).lower()

    def label(self, kind):
        value = self.data.get(kind)
        table = {"equipment": EQUIPMENT_LABELS, "level": LEVEL_LABELS, "force": FORCE_LABELS,
                 "mechanic": MECHANIC_LABELS, "kind": KIND_LABELS}[kind]
        return table.get(value, value) if value else None

    @property
    def primary_labels(self):
        return [MUSCLE_LABELS[m] for m in self.primary]

    @property
    def secondary_labels(self):
        return [MUSCLE_LABELS[m] for m in self.secondary]


@cache
def _load(path=DATA_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def entries():
    return [LibraryEntry(d) for d in _load()]


@cache
def _by_slug():
    return {d["slug"]: LibraryEntry(d) for d in _load()}


def get(slug):
    return _by_slug().get(slug) if slug else None


def muscle_label(key):
    return MUSCLE_LABELS.get(key, key)
