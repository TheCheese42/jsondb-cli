import argparse
import os
import shlex
import sys
from contextlib import suppress
from pathlib import Path
from textwrap import dedent
from typing import Iterable, Optional, Union

from . import model
from .version import version_string

SUPPRESS_WARNINGS = False


def prompt_continue() -> None:
    """Prompt the user to press enter to continue."""
    input("Press ENTER to continue...")


def validate_path(path: Optional[Union[str, Path]]) -> Path:
    if path is None:
        print(
            "[CRITICAL] The specified database could not be found."
        )
        sys.exit(4)
    return Path(path)


def database_does_not_exist(name: str, path: Union[str, Path]) -> None:
    print(
        f"[CRITICAL] The registered database {name} at "
        f"{path} doesn't exist."
    )
    sys.exit(3)


def invalid_tags(tags: Iterable[str]) -> None:
    print(
        f"[ERROR] The following tags weren't registered: {', '.join(tags)}."
    )
    sys.exit(7)


def invalid_attrs_format(entry: str) -> None:
    print(
        f"[ERROR] Invalid --attr: '{entry}' (Should be of format 'KEY:VALUE')."
    )
    sys.exit(8)


def index_out_of_bounds(index: int) -> None:
    print(f"[ERROR] Index {index} does not exist.")
    sys.exit(9)


def invalid_index(index: int) -> None:
    print(f"[ERROR] Index {index} is not a valid integer.")
    sys.exit(10)


def gen_browse_table(
    db: model.Database,
    page: int = 0,
    page_length: int = 10,
    filter_tags: Iterable[str] = (),
) -> tuple[str, list[int]]:
    """
    Generate a table with data from a given database.

    :param db: The database to take data from
    :type db: model.Database
    :param page: The current page of the table, defaults to 0
    :type page: int, optional
    :param page_length: How many entries there are per page, defaults to 10
    :type page_length: int, optional
    :param filter_tags: An iterable of tags to filter the table for, defaults
    to ()
    :type filter_tags: Iterable[str], optional
    :return: A tuple with the generated table and a list of ids on the page
    :rtype: tuple[str, list[int]]
    """
    id_width = max(len(str(db.entries - 1)), 3)
    data_width = 90
    header = f"{' ' * (id_width - 2)}ID | DATA{' ' * (data_width - 5)}"
    sep = f"{'-' * (id_width + 1)}|{'-' * data_width}"
    rows: list[str] = []
    entry_range = range((start := page_length * page), start + page_length)
    filter_result = db.query(filter_tags)
    entries_on_page: list[int] = []
    for i in entry_range:
        try:
            entry = db.at_index(filter_result[i])
            entries_on_page.append(filter_result[i])
        except IndexError:
            continue
        if len(entry[0]) > data_width:
            data = entry[0][:data_width - 3] + "..."
        else:
            data = entry[0]
        rows.append(f"{filter_result[i]:0>{id_width}} | {data}")
    return "\n".join([header, sep, *rows]), entries_on_page


def gen_browse_data_entry(entry: model.DATA_ENTRY) -> str:
    data = f"\"{entry[0]}\"\n"
    tags = f"Tags: {', '.join(entry[1])}"
    attrs_strings = [f"{k}: {v}" for k, v in entry[2].items()]
    attrs = f"Attributes:\n    {'\n    '.join(attrs_strings)}"
    return "\n".join([data, tags, attrs])


def parse_attr_value(value: str) -> Union[str, int, float, bool]:
    """
    Parse an ATTR value from a string.

    :param value: The string value
    :type value: str
    :return: The parsed value
    :rtype: Union[str, int, float, bool]
    """
    if value.isdecimal():
        new_value: Union[str, int, float, bool] = int(value)
    else:
        try:
            new_value = float(value)
        except ValueError:
            if value.lower() == "true":
                new_value = True
            elif value.lower() == "false":
                new_value = False
            else:
                new_value = value
    return new_value


def sub_init(args: argparse.Namespace) -> None:
    try:
        db = model.Database(args.name, args.path)
    except FileExistsError:
        print(
            "[CRITICAL] A database with this name already exists in "
            f"{args.path or model.JSONDB_HOME_PATH}."
        )
        sys.exit(1)
    db.save()
    model.init_register_file()
    try:
        model.register_database(db.path)
    except RuntimeError:
        print(
            f"[ERROR] A database called '{args.name}' is already registered "
            "elsewhere."
        )
        sys.exit(2)


def sub_info(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    try:
        with model.Database.open(path) as db:
            actions_dict = {
                "tags": lambda: ", ".join(db.tags),
                "size": lambda: str(db.entries),
                "bytes": lambda: str(db.calc_bytes()),
                "path": lambda: str(db.path.resolve()),
                "backups_enabled": lambda: str(db.backups_enabled),
                "enforce_tags": lambda: str(db.enforce_tags),
            }
            # Type comments are due to lambdas, might get changed in future
            # mypy versions
            if not args.subject:
                message = (
                    f"Tags: {actions_dict['tags']()}\n"  # type: ignore[no-untyped-call]  # noqa
                    f"Size: {actions_dict['size']()}\n"  # type: ignore[no-untyped-call]  # noqa
                    f"Bytes: {actions_dict['bytes']()}\n"  # type: ignore[no-untyped-call]  # noqa
                    f"Path: {actions_dict['path']()}\n"  # type: ignore[no-untyped-call]  # noqa
                    f"Backups enabled: {actions_dict['backups_enabled']()}\n"  # type: ignore[no-untyped-call]  # noqa
                    f"Tags enforced: {actions_dict['enforce_tags']()}"  # type: ignore[no-untyped-call]  # noqa
                )
            else:
                message = actions_dict[args.subject]()  # type: ignore[no-untyped-call]  # noqa
    except FileNotFoundError:
        database_does_not_exist(args.name, path)
    print(message)


def sub_modify(args: argparse.Namespace) -> None:
    if args.enforce_tags and args.no_enforce_tags:
        print(
            "[ERROR] --enforce-tags and --no-enforce-tags are mutually "
            "exclusive."
        )
        sys.exit(5)
    if args.enable_backups and args.disable_backups:
        print(
            "[ERROR] --enable-backups and --disable_backups are mutually "
            "exclusive."
        )
        sys.exit(5)
    if args.add_tags and args.clear_tags and not SUPPRESS_WARNINGS:
        print(
            "[WARNING] --add-tag will be overridden by --clear-tags. Suppress "
            "this warning by setting the JSONDB_SUPPRESS_WARNINGS environment "
            "variable to 1."
        )
    path = model.find_database(args.name)
    path = validate_path(path)
    try:
        with model.Database.open(path) as db:
            if args.add_tags:
                db.add_tags(args.add_tags)
            if args.rm_tags:
                db.rm_tags(args.rm_tags)
            if args.clear_tags:
                db.clear_tags()
            if args.enforce_tags:
                db.enforce_tags = True
            if args.no_enforce_tags:
                db.enforce_tags = False
            if args.enable_backups:
                db.backups_enabled = True
            if args.disable_backups:
                db.backups_enabled = False
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_add_db(args: argparse.Namespace) -> None:
    try:
        model.register_database(args.path)
    except RuntimeError:
        print(
            f"[ERROR] A database with the name '{args.path.stem}' is already"
            "registered."
        )
        sys.exit(2)


def sub_rm_db(args: argparse.Namespace) -> None:
    try:
        model.unregister_database(args.name)
    except RuntimeError:
        print(
            f"[ERROR] The database {args.name} wasn't registered."
        )
        sys.exit(6)


def sub_dbs(args: argparse.Namespace) -> None:
    print("\n".join(map(str.strip, map(str, model.read_register_file()))))


def sub_set(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    attrs: dict[str, Union[str, int, float, bool]] = {}
    for entry in args.attrs:
        try:
            key, value = entry.split(":", 1)
        except ValueError:
            invalid_attrs_format(entry)
        value = parse_attr_value(value)
        attrs[key] = value
    try:
        with model.Database.open(path) as db:
            try:
                db.set(args.data, *args.tags, **attrs)
            except ValueError:
                invalid_tags(set(args.tags).difference(db.tags))
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_unset(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    try:
        with model.Database.open(path) as db:
            try:
                db.unset(args.index)
            except IndexError:
                index_out_of_bounds(args.index)
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_edit(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    attrs = {}
    for attr in args.attrs:
        key, value = attr.split(":")
        attrs[key] = parse_attr_value(value)
    try:
        with model.Database.open(path) as db:
            if not set(args.tags).issubset(db.tags) and db.enforce_tags:
                invalid_tags(args.tags)
            try:
                db.edit_id(
                    id=args.index,
                    data=args.data,
                    tags=args.tags or None,
                    attrs=attrs or None,
                )
            except IndexError:
                index_out_of_bounds(args.index)
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_shell(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    validate_path(path)
    allowed_commands = ["info", "modify", "set", "unset", "browse", "id",
                        "query", "format"]
    print(f"jsondb-cli {version_string} Shell")
    print("Enter 'help' for a detailed explanation of what can be done here.")
    while True:
        try:
            cmd = input(f"({args.name}) $ ")
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)
        if cmd == "help":
            available_commands = "- " + "\n- ".join(allowed_commands)
            print(
                f"This is the jsondb-cli {version_string} Shell.\n"
                "Here you can enter jsondb commands without having to type "
                "'jsondb' and the name parameter which is necessary for most "
                "commands. All commands using the 'name' parameter can be used"
                f" from here.\n\nAvailable commands:\n{available_commands}\n\n"
                "Example:\n$ info --size\n42\n"
            )
            continue
        elif cmd in ("exit", "quit"):
            sys.exit(0)
        try:
            cmd_args = shlex.split(cmd)
        except ValueError:
            print("[ERROR] No closing quotation found.")
            sys.exit(13)
        if not cmd_args:
            continue
        if cmd_args[0] not in allowed_commands:
            print(
                f"Invalid command {cmd_args[0]}. Enter 'help' for more info."
            )
            continue
        try:
            # Not the prettiest approach, especially for error messages, but
            # works effectively with low effort
            main([cmd_args[0], args.name, *cmd_args[1:]])
        except (SystemExit, Exception) as e:
            if not isinstance(e, SystemExit):
                print(f"{type(e)}: {e}")


def sub_browse(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    try:
        with model.Database.open(path) as db:
            page = 0
            page_length = 10
            while True:
                table, id_range = gen_browse_table(
                    db, page, page_length, args.filters
                )
                notice = f"Filtering for tags: {', '.join(args.filters)}\n"
                print(
                    f"\n{notice if args.filters else ''}"
                    f"\n{table}\n\n[ID] Select entry{' ' * 5}[N] Next{' ' * 5}"
                    f"[P] Previous{' ' * 5}[E] Exit\n"
                )
                try:
                    choice = input("> ")
                except (KeyboardInterrupt, EOFError):
                    print()
                    sys.exit(0)
                try:
                    id_choice = int(choice)
                except ValueError:
                    if choice.lower() in ("n", "next"):
                        page = min(
                            page + 1, max(db.entries - 1, 0) // page_length
                        )
                    elif choice.lower() in ("p", "previous", "prev"):
                        page = max(page - 1, 0)
                    elif choice.lower() in ("e", "exit", "quit"):
                        sys.exit(0)
                    else:
                        print(
                            "Invalid input. Please enter either an ID to "
                            "select, [N] for the next page or [P] for the "
                            "previous page."
                        )
                        prompt_continue()
                    continue
                if id_choice not in id_range:
                    print(f"Invalid ID {id_choice}.")
                    prompt_continue()
                    continue
                while True:
                    output = gen_browse_data_entry(db.at_index(id_choice))
                    print(
                        f"""\n{output}\n
[E <DATA>] Edit data
[A <TAGS>] Add tag (Can add multiple separated by whitespace)
[R <TAGS>] Remove tag (Can remove multiple separated by whitespace)
[S <ATTRS>] Set attribute (KEY:VALUE) (Can set multiple separated by \
whitespace)
[U <ATTRS>] Unset attribute (Can unset multiple separated by whitespace)
[D] Delete\n[C] Cancel\n[H] Help\n"""
                    )
                    try:
                        choice = input("> ")
                    except (KeyboardInterrupt, EOFError):
                        print()
                        sys.exit(0)
                    if choice.lower().startswith("e "):
                        data = choice.split(maxsplit=1)[1]
                        db.edit_id(id_choice, data=data)
                    elif choice.lower().startswith("a "):
                        tags = set(choice.split()[1:])
                        for tag in db.at_index(id_choice)[1]:
                            tags.add(tag)
                        db.edit_id(id_choice, tags=tags)
                    elif choice.lower().startswith("r "):
                        tags_to_remove = choice.split()[1:]
                        original_tags = db.at_index(id_choice)[1]
                        for tag in tags_to_remove:
                            with suppress(KeyError):
                                original_tags.remove(tag)
                        db.edit_id(id_choice, tags=original_tags)
                    elif choice.lower().startswith("s "):
                        attrs = choice.split()[1:]
                        attrs_dict: model.ATTRS = {}
                        for attr_string in attrs:
                            try:
                                key, value = attr_string.split(":")
                            except ValueError:
                                print(
                                    f"Invalid ATTR format: {attr_string} "
                                    "(Should be KEY:VALUE)"
                                )
                                continue
                            attrs_dict[key] = parse_attr_value(value)
                        original_attrs = db.at_index(id_choice)[2]
                        db.edit_id(
                            id_choice, attrs={**original_attrs, **attrs_dict}
                        )
                    elif choice.lower().startswith("u "):
                        attrs_to_remove = choice.split()[1:]
                        original_attrs = db.at_index(id_choice)[2]
                        for attr in attrs_to_remove:
                            original_attrs.pop(attr)
                        db.edit_id(id_choice, attrs=original_attrs)
                    elif choice.lower() in ("d", "delete"):
                        if not args.no_confirmation_prompt:
                            if input(
                                "Do you really want to delete the entry? "
                                "[y/N] "
                            ).lower() not in ("y", "yes", "1", "true"):
                                continue
                        db.unset(id_choice)
                        break
                    elif choice.lower() in (
                        "c", "cancel", "e", "exit", "quit"
                    ):
                        break
                    elif choice.lower() in ("h", "help"):
                        input("""\
Edit the data: [E <DATA>]
Example: 'E This is the updated data'

Add a tag to the entry: [A <TAGS>]
Example: 'A Tag1 Tag2 TagN'

Remove a tag from the entry: [R <TAGS>]
Example: 'R Tag1 Tag2 TagN'

Set an attribute to the entry: [S <ATTRS>]
Example: 'S Key1:Value1 Key2:Value2'

Remove an attribute of the entry: [U <ATTRS>]
Example: 'U Key1 Key2 KeyN'

Delete the entry: [D]

Cancel this operation: [C]

Press ENTER to continue...""")

    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_id(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    try:
        with model.Database.open(path) as db:
            try:
                match = db.id(args.data, args.contains, args.case_insensitive)
            except ValueError:
                print(f"Nothing found matching '{args.data}'")
                sys.exit(10)
        print(match)
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_query(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    try:
        with model.Database.open(path) as db:
            result = db.query(args.filters)
        print(",".join(map(str, result)))
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def sub_format(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    if args.indices:
        indices = args.indices
    else:
        if not sys.stdin.isatty():
            indices = sys.stdin.readline().strip()
        else:
            print(
                "[ERROR] Either use the --indices flag or pipe input through "
                "stdin."
            )
            sys.exit(12)
    try:
        with model.Database.open(path) as db:
            ids = []
            for index in indices.split(","):
                try:
                    ids.append(int(index.strip()))
                except ValueError:
                    invalid_index(index)
            try:
                output = db.format(ids, args.format, args.use_real_ids)
            except IndexError as e:
                index_out_of_bounds(int(e.__notes__[0]))
        print(output)
    except FileNotFoundError:
        database_does_not_exist(args.name, path)


def main(argv: Optional[list[str]] = None) -> None:
    global SUPPRESS_WARNINGS

    parser = argparse.ArgumentParser(
        prog="jsondb",
        description="A cli used to manage small, handy databases.\n\n"
                    "Supported environment variables:\n- "
                    "JSONDB_SUPPRESS_WARNINGS (Suppress all warnings)\n- "
                    "JSONDB_BACKUP_KEEP_COUNT (How many backups should be kept"
                    " per database)",
        epilog="GitHub: https://NotYou404/jsondb-cli",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"jsondb-cli {version_string}",
    )

    subparsers = parser.add_subparsers(
        title="subcommands"
    )

    init_help = "Initialize a new database."
    init = subparsers.add_parser(
        "init",
        help=init_help,
        description=init_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    init.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    init.add_argument(
        "-p",
        "--path",
        action="store",
        type=Path,
        required=False,
        default=None,
        dest="path",
        help="The directory where the database should be created.",
    )
    init.set_defaults(func=sub_init)

    info_help = "Obtain information about a database."
    info = subparsers.add_parser(
        "info",
        help=info_help,
        description=info_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    info.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    info.add_argument(
        "-s",
        "--subject",
        action="store",
        type=str,
        choices=["tags", "size", "bytes", "path",
                 "backups_enabled", "enforce_tags"],
        required=False,
        default=None,
        dest="subject",
        help="Get information about a specific thing. Leave empty to retrieve "
             "all available information. Choices are 'tags' (list of "
             "registered tags), 'size' (amount of entries), 'bytes' (amount "
             "of bytes it takes up as json string in memory), 'path' (The "
             "database path), 'backups_enabled' (wether backups are enabled), "
             "'enforce_tags' (wether tags are actually being enforced).",
    )
    info.set_defaults(func=sub_info)

    modify_help = "Modify an existing database."
    modify = subparsers.add_parser(
        "modify",
        help=modify_help,
        description=modify_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    modify.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    modify.add_argument(
        "-t",
        "--add-tag",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="add_tags",
        help="Add a tag to the list of allowed tags. May be used multiple "
             "times.",
    )
    modify.add_argument(
        "-r",
        "--rm-tag",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="rm_tags",
        help="Remove a tag from the list of allowed tags. May be used multiple"
             " times.",
    )
    modify.add_argument(
        "--clear-tags",
        action="store_true",
        required=False,
        default=False,
        dest="clear_tags",
        help="Clear all tags from the list of allowed tags. Mutually exclusive"
             " with --add-tag and --rm-tag.",
    )
    modify.add_argument(
        "--enforce-tags",
        action="store_true",
        required=False,
        default=False,
        dest="enforce_tags",
        help="Enforce the tags in the list of allowed tags. When setting new "
             "values, this will raise an error if the value has a tag not in "
             "the list.",
    )
    modify.add_argument(
        "--no-enforce-tags",
        action="store_true",
        required=False,
        default=False,
        dest="no_enforce_tags",
        help="Do not enforce tags anymore."
    )
    modify.add_argument(
        "--enable-backups",
        action="store_true",
        required=False,
        default=False,
        dest="enable_backups",
        help="Enable backups to be made after every change. Will keep up to "
             "20 Backups per database, unless otherwise specified using the "
             "JSONDB_BACKUP_KEEP_COUNT environment variable.",
    )
    modify.add_argument(
        "--disable-backups",
        action="store_true",
        required=False,
        default=False,
        dest="disable_backups",
        help="Disable making backups after every change.",
    )
    modify.set_defaults(func=sub_modify)

    add_db_help = "Add a database file to the list of registered databases."
    add_db = subparsers.add_parser(
        "add-db",
        help=add_db_help,
        description=add_db_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    add_db.add_argument(
        "path",
        action="store",
        type=Path,
        help="The full path to the .jsondb file.",
    )
    add_db.set_defaults(func=sub_add_db)

    rm_db_help = "Remove a database file from the list of registered " \
                 "databases."
    rm_db = subparsers.add_parser(
        "rm-db",
        help=rm_db_help,
        description=rm_db_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    rm_db.add_argument(
        "name",
        action="store",
        type=str,
        help="The database name (filename without extension).",
    )
    rm_db.set_defaults(func=sub_rm_db)

    dbs_help = "List all registered databases, one per line."
    dbs = subparsers.add_parser(
        "dbs",
        help=dbs_help,
        description=dbs_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    dbs.set_defaults(func=sub_dbs)

    set_help = "Set new data to a database."
    set_ = subparsers.add_parser(
        "set",
        help=set_help,
        description=set_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    set_.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    set_.add_argument(
        "data",
        action="store",
        type=str,
        help="The data to be added to the database. Data is always stored as "
             "string.",
    )
    set_.add_argument(
        "-t",
        "--tag",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="tags",
        help="A tag that should be assigned to the data. Can be used multiple "
             "times.",
    )
    set_.add_argument(
        "-a",
        "--attr",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="attrs",
        help="A key: value pair that should be kept in the data's attributes. "
             "Should be of format `KEY:VALUE` (KEY may not contain a colon). "
             "VALUE may be either any string, an integer, a float or a boolean"
             " (\"True\", \"False\"). Can be used multiple times.",
    )
    set_.set_defaults(func=sub_set)

    unset_help = "Delete a data entry by its ID/index."
    unset = subparsers.add_parser(
        "unset",
        help=unset_help,
        description=unset_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    unset.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    unset.add_argument(
        "index",
        action="store",
        type=int,
        help="The index of the data entry to be deleted. Negative indices are "
             "allowed.",
    )
    unset.set_defaults(func=sub_unset)

    edit_help = "Edit a database entry."
    edit = subparsers.add_parser(
        "edit",
        help=edit_help,
        description=edit_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    edit.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    edit.add_argument(
        "index",
        action="store",
        type=int,
        help="The index of the entry to modify."
    )
    edit.add_argument(
        "-d",
        "--data",
        action="store",
        type=str,
        required=False,
        default=None,
        help="The new data.",
    )
    edit.add_argument(
        "-t",
        "--tag",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="tags",
        help="A tag that should be assigned to the data. Previous tags are "
             "being removed. Can be used multiple times.",
    )
    edit.add_argument(
        "-a",
        "--attr",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="attrs",
        help="A key: value pair that should be kept in the data's attributes. "
             "Should be of format `KEY:VALUE` (KEY may not contain a colon). "
             "VALUE may be either any string, an integer, a float or a boolean"
             " (\"True\", \"False\"). All previous attributes are being "
             "removed. Can be used multiple times.",
    )
    edit.set_defaults(func=sub_edit)

    shell_help = "Enter a REPL where all commands work without the name " \
                 "parameter."
    shell = subparsers.add_parser(
        "shell",
        help=shell_help,
        description=shell_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    shell.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    shell.set_defaults(func=sub_shell)

    browse_help = "Browse the database."
    browse = subparsers.add_parser(
        "browse",
        help=browse_help,
        description=browse_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    browse.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    browse.add_argument(
        "-f",
        "--filter",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="filters",
        help="A tag to filter results by. Can be used multiple times.",
    )
    browse.add_argument(
        "--no-confirmation-prompt",
        action="store_true",
        required=False,
        default=False,
        dest="no_confirmation_prompt",
        help="Disable asking for confirmation when deleting an entry.",
    )
    browse.set_defaults(func=sub_browse)

    id_help = (
        "Get the ID/index for a data entry. This will return the first "
        "occurrence of the literal data. For more fine-grained control, "
        "see the browse and query subcommands."
    )
    id = subparsers.add_parser(
        "id",
        help=id_help,
        description=id_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    id.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    id.add_argument(
        "data",
        action="store",
        type=str,
        help="The literal data to search for. Must perfectly match the "
             "demanded entry.",
    )
    id.add_argument(
        "-c",
        "--contains",
        action="store_true",
        required=False,
        default=False,
        dest="contains",
        help="It's enough when DATA is a substring of the entry.",
    )
    id.add_argument(
        "-i",
        "--case-insensitive",
        action="store_true",
        required=False,
        default=False,
        dest="case_insensitive",
        help="Search is now case-insensitive.",
    )
    id.set_defaults(func=sub_id)

    query_help = (
        "Get a list of all IDs/indices matching the filter criteria. "
        "Returns the IDs/indices separated by commas so they can easily "
        "parsed or fed into the format subcommand.\n\nExample: "
        "jsondb query database1 -f tag1 | jsondb format database1"
    )
    query = subparsers.add_parser(
        "query",
        help=query_help,
        description=query_help,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    query.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    query.add_argument(
        "-f",
        "--filter",
        action="append",
        type=str,
        required=False,
        default=[],
        dest="filters",
        help="A tag to filter results by. Can be used multiple times.",
    )
    query.set_defaults(func=sub_query)

    format_help = (
        "Output formatted data for provided IDs/indices, one per line "
        "using a format string."
    )
    format_ = subparsers.add_parser(
        "format",
        help=format_help,
        description=format_help,
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="For a more readable description of the --format flag, see "
               "https://github.com/NotYou404/jsondb-cli/blob/main/Format.md"
    )
    format_.add_argument(
        "name",
        action="store",
        type=str,
        help="The name of the database (without the .jsondb extension).",
    )
    format_.add_argument(
        "-i"
        "--indices",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="indices",
        help="A list of indices separated by commas. If not set, this will "
             "read input from stdin, allowing for passing output from query "
             "into this.",
    )
    format_.add_argument(
        "-f",
        "--format",
        action="store",
        type=str,
        required=False,
        default=None,
        dest="format",
        help=dedent(f"""
        A format string used to format the data entries.

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

        The default format string is '{model.DEFAULT_FORMAT_STRING}'
        """).replace("%", "%%")
    )
    format_.add_argument(
        "--use-real-ids",
        action="store_true",
        required=False,
        default=False,
        dest="use_real_ids",
        help="Use the original indices as in the database as ID. Otherwise, "
             "this would start counting from 0.",
    )
    format_.set_defaults(func=sub_format)

    SUPPRESS_WARNINGS = bool(os.getenv("JSONDB_SUPPRESS_WARNINGS"))
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
