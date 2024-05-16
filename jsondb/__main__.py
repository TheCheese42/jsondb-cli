import argparse
import sys
from pathlib import Path
from textwrap import dedent
from typing import Optional, Union, Iterable
from . import model
from .version import version_string
import os


SUPPRESS_WARNINGS = False


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
    print("\n".join(map(str, model.read_register_file())))


def sub_set(args: argparse.Namespace) -> None:
    path = model.find_database(args.name)
    path = validate_path(path)
    attrs: dict[str, Union[str, int, float, bool]] = {}
    for entry in args.attrs:
        try:
            key, value = entry.split(":", 1)
        except ValueError:
            invalid_attrs_format(entry)
        if value.isdecimal():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
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
        cmd_args = cmd.split()
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
    ...


def sub_id(args: argparse.Namespace) -> None:
    ...


def sub_query(args: argparse.Namespace) -> None:
    ...


def sub_format(args: argparse.Namespace) -> None:
    ...


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
        nargs=1,
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
        nargs=1,
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
        nargs=1,
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
        nargs=1,
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
        nargs=1,
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
        nargs=1,
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
