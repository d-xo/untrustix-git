#! /usr/bin/env python3

from base64 import b32encode
from doctest import testmod
from hashlib import sha256
from pathlib import Path
from subprocess import run
from tempfile import NamedTemporaryFile, mkdtemp
from typing import Optional, List
from uuid import uuid4 as uuid

import pygit2 as git  # type: ignore

# --- test data ---


def store_hash(seed: Optional[str] = None) -> str:
    """
    hash `seed` using the nix store hash format. `seed` is random if not provided

    >>> store_hash("1")
    'xajasisp7xdgy1fvxhm3rbia7wxazaf9'
    """
    if seed is None:
        seed = uuid().hex

    with NamedTemporaryFile() as f:
        f.write(f"{seed}".encode("utf-8"))
        f.seek(0)
        return str(
            run(
                [
                    "nix-hash",
                    "--type",
                    "sha256",
                    "--truncate",
                    "--base32",
                    "--flat",
                    f.name,
                ],
                capture_output=True,
            )
            .stdout.strip()
            .decode("utf-8")
        )


def nar_hash(seed: Optional[str] = None) -> str:
    """
    hash `seed` using using sha256. `seed` is random if not provided

    >>> nar_hash("1")
    '6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b'
    """
    if seed is None:
        seed = uuid().hex

    return sha256(f"{seed}".encode("utf-8")).hexdigest()


def create_repo() -> git.Repository:
    """create a git repo in a new temporary directory. configure it to allow for partial clones"""
    d = mkdtemp()
    repo = git.init_repository(d, bare=True)

    # add partial clone support
    conf = repo.config
    conf["uploadpack.allowfilter"] = 1
    conf["uploadpack.allowanysha1inwant"] = 1

    return repo


# --- repo utils ---


def shards(path: str, depth: int = 5) -> List[str]:
    """
    returns the list of directories that a given store path will be written to

    >>> shards("xajasisp7xdgy1fvxhm3rbia7wxazaf9")
    ['xa', 'ja', 'si', 'sp', '7x', 'dgy1fvxhm3rbia7wxazaf9']

    >>> shards("xajasisp7xdgy1fvxhm3rbia7wxazaf9", depth=3)
    ['xa', 'ja', 'si', 'sp7xdgy1fvxhm3rbia7wxazaf9']
    """
    shards = []
    for i in range(0, depth):
        shards.append(path[2 * i : 2 * i + 2])
    shards.append(path[2 * depth :])
    return shards


def update_tree(
    repo: git.Repository, tree: git.Oid, path: List[str], content: str
) -> git.Oid:
    """
    adds a blob with `content` at `path` to `tree` in `repo`

    >>> repo = create_repo()
    >>> tree = repo.TreeBuilder().write()
    >>> for i in range(10):
    ...    path = store_hash(f"{i}")
    ...    content = nar_hash(path)
    ...    tree = update_tree(repo, tree, shards(path), content)
    >>> print(tree)
    00f68bdb866b654d4ce3da90609b74137605bd90
    """
    # subdir exists: recurse
    for entry in repo.get(tree):
        if entry.name is path[0] and entry.type is "tree":
            sub = update_tree(repo, entry.id, path[1:], content)
            builder = repo.TreeBuilder(repo.get(tree))
            builder.remove(path[0])
            builder.insert(path[0], sub, git.GIT_FILEMODE_TREE)
            return builder.write()

    # subdir does not exist: create required objects
    if len(path[0]) is 2:
        sub = update_tree(repo, tree, [path[-1]], content)
        for d in reversed(path[1:-1]):
            builder = repo.TreeBuilder()
            builder.insert(d, sub, git.GIT_FILEMODE_TREE)
            sub = builder.write()

        builder = repo.TreeBuilder(repo.get(tree))
        builder.insert(path[0], sub, git.GIT_FILEMODE_TREE)
        return builder.write()

    # path[0] is not a subdir: write blob
    else:
        blob = repo.write(git.GIT_OBJ_BLOB, content)
        builder = repo.TreeBuilder()
        builder.insert(path[0], blob, git.GIT_FILEMODE_BLOB)
        return builder.write()


# --- test ---

if __name__ == "__main__":
    testmod()
