#! /usr/bin/env python3

from pathlib import Path
from hashlib import sha256
from subprocess import run
from uuid import uuid1 as uuid
from typing import List
import tempfile

import pygit2 as git # type: ignore

# --- test data ---

# generates a random nix-store hash
def store_hash() -> str:
    with tempfile.NamedTemporaryFile() as f:
        f.write(f"{uuid()}".encode('utf-8'))
        f.seek(0)
        return str(run(
            ["nix-hash", "--type", "sha256", "--truncate", "--base32", "--flat", f.name],
            capture_output=True
        ).stdout.strip().decode('utf-8'))


# generates a random full length sha256 hash
def nar_hash() -> str:
    return sha256(uuid().hex.encode('utf-8')).hexdigest()

# --- merkleised log ---

def store_leaf(repo: git.Repository, name: str, content: str) -> git.Oid:
    """leaves are tree objects containing a single file"""
    blob = repo.create_blob(content)
    tree = repo.TreeBuilder()
    tree.insert(name, blob, git.GIT_FILEMODE_BLOB)
    return tree.write()

def pivot(n: int) -> int:
    """find the highest power of 2 less than n"""
    res = 0;
    for i in range(n - 1, 0, -1):
        # If i is a power of 2
        if ((i & (i - 1)) == 0):
            res = i;
            break;
    return res;

def merkleise(repo: git.Repository, leaves: List[git.Oid]) -> git.Oid:
    """build a merkle tree following the spec in RFC6962"""
    if len(leaves) == 1:
        return leaves[0]

    k = pivot(len(leaves))
    tree = repo.TreeBuilder()
    tree.insert('l', merkleise(repo, leaves[0:k]), git.GIT_FILEMODE_TREE)
    tree.insert('r', merkleise(repo, leaves[k:len(leaves)]), git.GIT_FILEMODE_TREE)
    return tree.write()

# --- testing ---

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    repo = git.init_repository(d, bare=True)
    leaves = [store_leaf(repo, store_hash(), nar_hash()) for _ in range(1,100)]
    root = merkleise(repo, leaves)
