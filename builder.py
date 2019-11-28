#! /usr/bin/env python3

from argparse import ArgumentParser
from base64 import b32encode
from doctest import testmod
from hashlib import sha256
from pathlib import Path
from subprocess import run
from tempfile import NamedTemporaryFile, mkdtemp
from time import time, ctime
from typing import Optional, List
from uuid import uuid4 as uuid

import pygit2 as git  # type: ignore

import common

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
    directory = mkdtemp()
    repo = git.init_repository(directory, bare=True)

    # add partial clone support
    conf = repo.config
    conf["uploadpack.allowfilter"] = 1
    conf["uploadpack.allowanysha1inwant"] = 1

    return repo


# --- repo utils ---


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
    ...    tree = update_tree(repo, tree, common.shards(path, depth=5), content)
    >>> print(tree)
    00f68bdb866b654d4ce3da90609b74137605bd90
    """
    for entry in repo.get(tree):
        # subdir exists: recurse
        if (entry.name == path[0]) and (entry.type == "tree"):
            sub = update_tree(repo, entry.id, path[1:], content)
            builder = repo.TreeBuilder(repo.get(tree))
            builder.remove(path[0])
            builder.insert(path[0], sub, git.GIT_FILEMODE_TREE)
            return builder.write()

    # subdir does not exist: create required objects
    if len(path) > 1:
        # write leaf node
        sub = update_tree(repo, repo.TreeBuilder().write(), [path[-1]], content)
        # build intermediate nodes
        for d in reversed(path[1:-1]):
            builder = repo.TreeBuilder()
            builder.insert(d, sub, git.GIT_FILEMODE_TREE)
            sub = builder.write()

        # attach to `tree`
        builder = repo.TreeBuilder(repo.get(tree))
        builder.insert(path[0], sub, git.GIT_FILEMODE_TREE)
        return builder.write()

    # path[0] is not a subdir: write blob
    elif len(path) == 1:
        blob = repo.write(git.GIT_OBJ_BLOB, content)
        builder = repo.TreeBuilder(repo.get(tree))
        builder.insert(path[0], blob, git.GIT_FILEMODE_BLOB)
        return builder.write()

    else:
        raise Exception(f"invalid path: {path}")


def advance_master(
    repo: git.Repository,
    parents: List[git.Oid],
    tree: git.Oid,
    when: Optional[int] = None,
    msg: Optional[str] = None,
) -> git.Oid:
    if when is None:
        when = int(time())
    if msg is None:
        msg = ""

    return repo.create_commit(
        "refs/heads/master",
        git.Signature(name="untrustix", email="untrust@ix.com", time=when),
        git.Signature(name="untrustix", email="untrust@ix.com", time=when),
        msg,
        tree,
        parents,
    )


# --- test ---

if __name__ == "__main__":

    # ------------------------------------------

    testmod()  # run tests

    # ------------------------------------------

    parser = ArgumentParser("untrustix-git builder")
    parser.add_argument(
        "--repo_path", help="The on disk location of the git repository", type=str
    )
    parser.add_argument(
        "--sharding_depth", help="The sharding depth to be used", type=int, default=2
    )
    args = parser.parse_args()

    repo: Optional[git.Repository] = None
    commit: Optional[git.Oid] = None
    if args.repo_path:
        repo = git.Repository(args.repo_path)
        commit = repo.head.resolve().target
    else:
        repo = create_repo()
        tree = repo.TreeBuilder().write()
        commit = advance_master(repo=repo, parents=[], tree=tree, when=0, msg="init")

    print(f"writing to repo at {repo.path}")

    while True:
        when = repo.get(commit).commit_time + 1
        path = store_hash(f"{when}")
        content = nar_hash(path)
        tree = update_tree(
            repo, repo.get(commit).tree.id, common.shards(path, args.sharding_depth), content
        )
        commit = advance_master(
            repo=repo, parents=[commit], tree=tree, when=when, msg=f"{path} {content}"
        )
        if when % 1000 == 0:
            print(when, ctime())
