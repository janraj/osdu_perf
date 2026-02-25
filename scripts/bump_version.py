import argparse
import pathlib
import re
from dataclasses import dataclass

VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


@dataclass
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = VERSION_PATTERN.match(value.strip())
        if not match:
            raise ValueError(f"Unsupported version format: {value}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )

    def bump(self, bump_type: str) -> "Version":
        if bump_type == "major":
            return Version(self.major + 1, 0, 0)
        if bump_type == "minor":
            return Version(self.major, self.minor + 1, 0)
        if bump_type == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"Unsupported bump type: {bump_type}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def replace_version(file_path: pathlib.Path, pattern: str, new_version: str) -> None:
    content = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, rf"\g<1>{new_version}\g<3>", content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Unable to update version in {file_path}")
    file_path.write_text(updated, encoding="utf-8")


def read_current_version(pyproject_file: pathlib.Path) -> str:
    content = pyproject_file.read_text(encoding="utf-8")
    match = re.search(r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")\s*$', content, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Unable to locate project version in pyproject.toml")
    return match.group(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump project version")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], required=True)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    pyproject_file = root / "pyproject.toml"
    setup_file = root / "setup.py"
    init_file = root / "osdu_perf" / "__init__.py"

    current = Version.parse(read_current_version(pyproject_file))
    next_version = str(current.bump(args.bump))

    replace_version(pyproject_file, r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")\s*$', next_version)
    replace_version(setup_file, r'^(\s*version\s*=\s*")(\d+\.\d+\.\d+)(",)\s*$', next_version)
    replace_version(init_file, r'^(__version__\s*=\s*")(\d+\.\d+\.\d+)(")\s*$', next_version)

    print(f"CURRENT_VERSION={current}")
    print(f"NEW_VERSION={next_version}")


if __name__ == "__main__":
    main()
