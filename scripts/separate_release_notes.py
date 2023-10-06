from argparse import ArgumentParser
import os
import re


def load_file(location: str) -> str:
    if os.path.isdir(location):
        location = location + "/CHANGELOG.md"
    if not os.path.exists(location):
        raise ValueError(f"no changelog at {location}")

    with open(location, "r", encoding="ascii") as changelog:
        return changelog.read()


def separate_log(changelog: str, version: str) -> str:
    headerPattern = r"## \[v[\d.]+\] \d{4}-\d{2}-\d{2}"
    versionHeaders = re.search(headerPattern, changelog)
    if versionHeaders and version not in versionHeaders[0]:
        raise ValueError(f"""
version {version} not found in format'## [{version}] at head of changelog
        """)
    return re.split(headerPattern, changelog)[1]


def main():
    parser = ArgumentParser(
        prog="release_notes",
        description="""
splits out the currently active release notes
        """,
    )
    parser.add_argument(
        "version",
        type=str
    )
    parser.add_argument(
        "-l",
        "--location",
        type=str,
        default="./CHANGELOG.md"
    )
    parsed = parser.parse_args()
    version = parsed.version
    location = parsed.location

    fileString = load_file(location)
    log_entry = separate_log(fileString, version)
    print(log_entry)


if __name__ == "__main__":
    main()
