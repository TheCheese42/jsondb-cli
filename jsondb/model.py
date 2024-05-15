import json
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterable, Optional, Union

from .version import __version__, version_string

TAGS = set[str]
ENFORCE_TAGS = bool
BACKUPS_ENABLED = bool
ATTRS = dict[str, Union[str, int, float, bool]]
DATA_ENTRY = tuple[str, TAGS, ATTRS]
DATA = list[DATA_ENTRY]
VERSION = str
STRUCTURE = dict[
    str,
    Union[TAGS, DATA, ENFORCE_TAGS, BACKUPS_ENABLED, VERSION]
]

DEFAULT_FORMAT_STRING = '[%id(3)] "%data()" (%tags(", ")) (%attrs(": ","; "))'
JSONDB_HOME_PATH = Path.home() / "Documents" / "jsondb"


class Database:
    def __init__(
        self,
        name: str,
        dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if dir is None:
            dir = JSONDB_HOME_PATH

        self.path = Path(dir) / name
        if self.path.exists():
            raise FileExistsError(f"The file {self.path} already exists.")
        self.path.mkdir(exist_ok=True)
        self.path.touch()

        self._structure: STRUCTURE = self.empty()
        self._tags: TAGS = self._structure["tags"]  # type: ignore[assignment]
        self._enforce_tags: bool = self._structure["enforce_tags"]  # type: ignore[assignment] # noqa
        self._backups_enabled: bool = self._structure["backups_enabled"]  # type: ignore[assignment] # noqa
        self._data: DATA = self._structure["data"]  # type: ignore[assignment]

    @classmethod
    @contextmanager
    def open(cls, path: Union[str, Path]) -> Generator["Database", None, None]:
        path = Path(path)

        with open(path, "r", encoding="utf-8") as fp:
            json_ = fp.read()

        db = Database.__new__(Database)
        db.path = Path(path)
        structure = json.loads(json_)
        if __version__ < tuple(map(int, structure["version"].split("."))):
            print(
                f"[WARNING] The database at {path} was last modified by jsondb"
                f" version {structure['version']}, which is newer than the "
                f"currently installed ({version_string}). Please consider "
                "upgrading."
            )
        db._structure = structure
        db._tags = structure["tags"]
        db._enforce_tags = structure["enforce_tags"]
        db._backups_enabled = structure["backups_enabled"]
        db._data = structure["data"]

        if db.backups_enabled:
            backup_dir = path.parent / f".jsondb_backups_{path.stem}"
            backup_dir.mkdir(exist_ok=True)
            timestamp = int(time.time())
            with open(
                backup_dir / f".jsondb_backup_{path.stem}_{timestamp}.jsondb",
                mode="w",
                encoding="utf-8",
            ) as fp:
                fp.write(json_)

        try:
            yield db
        finally:
            db.save()

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(self.build_structure(), fp)

    def build_structure(self) -> STRUCTURE:
        return {
            "tags": self._tags,
            "enforce_tags": self._enforce_tags,
            "backups_enabled": self._backups_enabled,
            "data": self._data,
            "version": ".".join(map(str, __version__)),
        }

    @property
    def enforce_tags(self) -> bool:
        """
        Wether tags should actually be enforced or one could just use any tag,
        no matter if it's specified in tags.
        """
        return self._enforce_tags

    @enforce_tags.setter
    def enforce_tags(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("enforce_tags must be a boolean")
        self._enforce_tags = value

    @property
    def backups_enabled(self) -> bool:
        """
        Wether backups are being made before every change. Those will reside in
        a .jsondb_backups_<database> folder next to the database itself.
        """
        return self._backups_enabled

    @backups_enabled.setter
    def backups_enabled(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("backups_enabled must be a boolean")
        self._backups_enabled = value

    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the list of allowed tags. Those are only enforced if
        `enforce_tags` is set to True.

        :param tag: The tag to be added to the list. Dupes are being silently
        ignored
        :type tag: str
        :raises TypeError: The tag isn't a string
        """
        if not isinstance(tag, str):
            raise TypeError("tag must be a string")
        self._tags.add(tag)

    def rm_tag(self, tag: str) -> None:
        """
        Remove a tag from the list of allowed tags. Those are only enforced if
        `enforce_tags` is set to True.

        :param tag: The tag to be removed from the list. Won't error if tag is
        not in the list of tags.
        :type tag: str
        """
        try:
            self._tags.remove(tag)
        except KeyError:
            pass

    def clear_tags(self) -> None:
        """
        Clear all tags from the list of allowed tags.
        """
        self._tags.clear()

    def add_tags(self, tags: Iterable[str]) -> None:
        """
        Add multiple tags at once.

        See also: `Database.add_tag()`

        :param tags: A list of tags to be added all at once
        :type tags: list[str]
        """
        for tag in tags:
            self.add_tag(tag)

    def rm_tags(self, tags: list[str]) -> None:
        """
        Remove multiple tags at once.

        See also: `Database.rm_tag()`

        :param tags: A list of tags to be removed all at once.
        :type tags: list[str]
        """
        for tag in tags:
            self.rm_tag(tag)

    def set(
        self,
        data: str,
        *tags: str,
        **attrs: Union[str, int, float, bool],
    ) -> None:
        """
        Add a data entry to the database. Tags can be added as further
        positional arguments (`*tags`) and attributes as keyword arguments
        (`**attrs`).

        Positional arguments (`*tags`) must be of type str.
        Keyword arguments (`**attrs`) must be of type str, int, float or bool.

        :param data: The data to be added to the database.
        :type data: str
        :raises TypeError: data is not a string
        :raises TypeError: At least one tag isn't a string
        :raises ValueError: At least one tag isn't in the list of allowed tags
        (only if `enforce_tags` is set to True)
        :raises TypeError: At least one attribute key is not a string
        :raises TypeError: At least one attribute value is not of type str,
        int, float or bool
        """
        if not isinstance(data, str):
            raise TypeError("data must be a string")
        for tag in tags:
            if not isinstance(tag, str):
                raise TypeError("All tags must be strings")
            if self.enforce_tags:
                if tag not in self._tags:
                    raise ValueError(f"Tag {tag} not in allowed tags")
        for key, value in attrs.items():
            if not isinstance(key, str):
                raise TypeError("All attribute keys must be strings")
            if (
                not isinstance(value, str)
                and not isinstance(value, int)
                and not isinstance(value, float)
                and not isinstance(value, bool)
            ):
                raise TypeError(
                    "All attribute values must be either strings, integers, "
                    "floats or booleans"
                )

        self._data.append((data, set(tags), attrs))

    def unset(self, index: int) -> None:
        if not isinstance(index, int):
            raise TypeError("index must be an integer")
        try:
            del self._data[index]
        except IndexError:
            raise IndexError(f"Index {index} does not exist")

    def id(self, data: str) -> int:
        for i, entry in enumerate(self._data):
            if data == entry[0]:
                return i
        else:
            raise ValueError(f"'{data}' is not in the database.")

    def query(self, tags: Iterable[str]) -> list[int]:
        """
        Query the database by filtering for specific tags.

        :param tags: An iterable of tags used as filter
        :type tags: Iterable[str]
        :return: A list of indices where the queried data can be found
        :rtype: list[int]
        """
        ids: list[int] = []
        tags = set(tags)
        for i, entry in enumerate(self._data):
            if tags.issubset(entry[1]):
                ids.append(i)
        return ids

    def at_index(self, index: int) -> DATA_ENTRY:
        """
        Get a data entry from an index.

        :param index: The index/id where the data entry lies at
        :type index: int
        :raises IndexError: The specified index is not in the database
        :return: A tuple of the data string, the set of tags and the attributes
        dictionary
        :rtype: DATA_ENTRY
        """
        try:
            out = self._data[index]
        except IndexError:
            raise IndexError(f"Index {index} does not exist")
        return out

    def format(
        self,
        ids: Iterable[int],
        fmt_string: Optional[str] = None,
        use_real_ids: bool = False,
    ) -> str:
        """
        Format specified database entries using a format string, one per line.

        The format string may contain the following macros:

        `%id(WIDTH, "FILL_CHAR")`:
        - WIDTH (optional): A fixed width for the id, defaults to 0
        (No fixed width)
        - FILL_CHAR (optional): If a fixed WIDTH is set, this fills the
        padding, defaults to `"0"`
        - Example: `%id(3, "0")` -> `001`, `002`, etc.

        `%data(WIDTH, "FILL_CHAR")`:
        - WIDTH (optional): A fixed width for the data, defaults to 0
        (No fixed width)
        - FILL_CHAR (optional): If a fixed WIDTH is set, this fills the
        padding, defaults to `" "`
        - Example: `%data(12, "⋅")` -> `"Good data⋅⋅⋅"`, `"Better data⋅"`, etc.

        `%tags("SEP")`:
        - SEP (required): A separator between tag
        - Example: `%tags(", ")` -> `Tag1, Tag2, TagN`

        `%attrs("SEP1", "SEP2")`:
        - SEP1 (required): The separator between key and value
        - SEP2 (required): The separator between two key-value pairs
        - Example: `%attrs(": ", "; ")` -> `Key1: Value1; Key2: Value2`

        :param ids: An iterable of ids to be formatted
        :type ids: Iterable[int]
        :param fmt_string: The format string specifier used to format the
        entries, defaults to
        `'[%id(3)] "%data()" (%tags(", ")) (%attrs(": ","; "))'`
        :type fmt_string: str, optional
        :param use_real_ids: Wether to use the actual database indices.
        Otherwise it will start counting from 0, defaults to False
        :type use_real_ids: bool, optional
        :raises TypeError: At least one id is not an integer
        :raises IndexError: At least one id does not exist
        :return: The formatted string
        :rtype: str
        """
        if fmt_string is None:
            final_fmt_string = DEFAULT_FORMAT_STRING
        else:
            final_fmt_string = fmt_string

        RE_ID = r"%id\((\d*)(,\s*\"(.*?)\")?\)"  # Group 1: WIDTH | Group 3: FILL_CHAR  # noqa
        RE_DATA = r"%data\((\d*)(,\s*\"(.*?)\")?\)"  # Group 1: WIDTH | Group 3: FILL_CHAR  # noqa
        RE_TAGS = r"%tags\(\"(.*?)\"\)"  # Group 1: SEP
        RE_ATTRS = r"%attrs\(\"(.*?)\",\s*\"(.*?)\"\)"  # Group 1: SEP1 | Group 2: SEP2  # noqa

        match_id = re.match(RE_ID, final_fmt_string)
        match_data = re.match(RE_DATA, final_fmt_string)
        match_tags = re.match(RE_TAGS, final_fmt_string)
        match_attrs = re.match(RE_ATTRS, final_fmt_string)

        lines = []

        for i, id in enumerate(ids):
            if not isinstance(id, int):
                raise TypeError("ids must be an iterable of integers")
            entry = self.at_index(id)  # May raise IndexError

            line = final_fmt_string
            if match_id:
                id_to_embed = id if use_real_ids else i
                width = match_id.group(1)
                filler = match_id.group(3) or 0
                line = line.replace(
                    match_id.group(0), f"{id_to_embed:{filler}>{width}}"
                )
            if match_data:
                width = match_data.group(1)
                filler = match_data.group(3) or " "
                data = '"' + entry[0] + '"'
                line = line.replace(
                    match_data.group(0), f"{data:{filler}<{width}}"
                )
            if match_tags:
                sep = match_tags.group(1)
                line = line.replace(
                    match_tags.group(0), sep.join(entry[1])
                )
            if match_attrs:
                sep1 = match_attrs.group(1)
                sep2 = match_attrs.group(2)
                attrs_strings: list[str] = []
                for key, value in entry[2].items():
                    attrs_strings.append(f"{key}{sep1}{value}")
                line = line.replace(
                    match_attrs.group(0), sep2.join(attrs_strings)
                )
            lines.append(line)

        return "\n".join(lines)

    def edit_id(
        self,
        id: int,
        data: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        attrs: Optional[ATTRS] = None,
    ) -> None:
        entry = self.at_index(id)
        new_entry = (
            data or entry[0],
            set(tags or entry[1]),
            attrs or entry[2],
        )
        self._data[id] = new_entry

    @staticmethod
    def empty() -> STRUCTURE:
        return {
            "tags": set(),
            "enforce_tags": False,
            "backups_enabled": False,
            "data": [],
            "version": ".".join(map(str, __version__)),
        }


def init_register_file(clear: bool = False) -> None:
    """
    Create the .paths register file in the Documents/jsondb directory. If
    present, this will do nothing.

    :param clear: This will wipe the current file, defaults to False
    :type clear: bool, optional
    """
    JSONDB_HOME_PATH.mkdir(exist_ok=True)
    path = JSONDB_HOME_PATH / ".paths"
    if not path.exists() or clear:
        with open(path, "w", encoding="utf-8"):
            pass


def read_register_file() -> list[Path]:
    """
    Returns a list of all database files registered.

    :returns: A list of database file paths
    :rtype: list[Path]
    """
    path = JSONDB_HOME_PATH / ".paths"
    with open(path, "r", encoding="utf-8") as fp:
        return [i for i in map(Path, fp.readlines()) if i]


def register_database(db: Union[Path, str]) -> None:
    """
    Register a database file.

    :param db: The path to the database file (commonly .jsondb)
    :type db: Union[Path, str]
    """
    db = Path(db)
    path = JSONDB_HOME_PATH / ".paths"
    with open(path, "r", encoding="utf-8") as fp:
        dbs = fp.readlines()
    for registered_db in dbs:
        if Path(registered_db).stem == db.stem:
            raise RuntimeError(
                f"A database with name {db.stem} exists already."
            )
    with open(path, "a", encoding="utf-8") as fp:
        fp.write(str(db.resolve()) + "\n")


def unregister_database(db: Union[Path, str]) -> None:
    """
    Unregister a database file.

    :param db: The path to the database file (commonly .jsondb)
    :type db: Union[Path, str]
    """
    db = Path(db)
    path = JSONDB_HOME_PATH / ".paths"
    with open(path, "r", encoding="utf-8") as fp:
        dbs = fp.readlines()
    dbs = [i for i in dbs if Path(i) != db]
    with open(path, "w", encoding="utf-8") as fp:
        fp.writelines(dbs)


def find_database(db: str) -> Path:
    """
    Find a database file path by its name.

    :param db: The name of the database (filename without suffix)
    :type db: str
    :returns: The database file path
    :rtype: Path
    :raises FileNotFoundError: The database file isn't registered
    """
    path = JSONDB_HOME_PATH / ".paths"
    with open(path, "r", encoding="utf-8") as fp:
        dbs = fp.readlines()
    for file in dbs:
        if Path(file).stem == db:
            return Path(file)
    raise FileNotFoundError(f"The database {db} is not registered")
