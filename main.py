#! /usr/bin/env python3

from hashlib import sha256
from subprocess import run
from uuid import uuid1 as uuid
from typing import List, Tuple
from functools import reduce, partial
import tempfile

import pygit2 as git # type: ignore

# --- test data ---

counter = 0

# generates a random nix-store hash
def store_hash() -> str:
    with tempfile.NamedTemporaryFile() as f:
        global counter
        f.write(f"{counter}".encode('utf-8'))
        counter = counter + 1
        f.seek(0)
        return str(run(
            ["nix-hash", "--type", "sha256", "--truncate", "--base32", "--flat", f.name],
            capture_output=True
        ).stdout.strip().decode('utf-8'))


# generates a random full length sha256 hash
def nar_hash() -> str:
    return sha256(f"{counter}".encode('utf-8')).hexdigest()

# --- merkleised log ---

def store_leaf(repo: git.Repository, name: str, content: str) -> git.Oid:
    """leaves are tree objects containing a single file"""
    tree = repo.TreeBuilder()
    tree.insert(name, repo.create_blob(content), git.GIT_FILEMODE_BLOB)
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

def join_trees(repo: git.Repository, left: git.Oid, right: git.Oid) -> git.Oid:
    tree = repo.TreeBuilder()
    tree.insert('l', left, git.GIT_FILEMODE_TREE)
    tree.insert('r', right, git.GIT_FILEMODE_TREE)
    tree.insert('.keep', repo.create_blob(""), git.GIT_FILEMODE_BLOB)
    return tree.write()

def merkleise(repo: git.Repository, leaves: List[git.Oid]) -> git.Oid:
    """build a merkle tree following the spec in RFC6962"""
    if len(leaves) == 1:
        return leaves[0]

    k = pivot(len(leaves))
    return join_trees(
        repo,
        merkleise(repo, leaves[0:k]),
        merkleise(repo, leaves[k:len(leaves)])
    )

# --- inclusion proofs ---

def get_leaves(repo: git.Repository, tree: git.Oid, leaves: List[git.Oid] = None) -> List[git.Oid]:
    """get all the leaves from a tree in order"""
    if leaves is None:
        leaves = []

    for entry in repo.get(tree):
        if entry.type == 'tree' and len(repo.get(entry.id)) == 1:
            leaves.append(entry.id)
        if entry.type == 'tree':
            leaves = get_leaves(repo, entry.id, leaves)

    return leaves


def path(repo: git.Repository, m: int, leaves: List[git.Oid]) -> List[Tuple[str, git.Oid]]:
    """build a merkle audit path following the spec in RFC6962"""
    n = len(leaves)
    k = pivot(n)

    if n == 1:
        return []
    elif m < k:
        return path(repo, m, leaves[0:k]) + [('r', merkleise(repo, leaves[k:n]))]
    elif m >= k:
        return path(repo, m - k, leaves[k:n]) + [('l', merkleise(repo, leaves[0:k]))]


def validate_path(repo: git.Repository, path: List[Tuple[str, git.Oid]], root: git.Oid) -> bool:
    assert path[0][0] in ['l', 'r', '']

    if len(path) is 1:
        return path[0][1] == root

    acc = ''
    if path[1][0] is 'r':
        acc = join_trees(repo, path[0][1] , path[1][1])
    if path[1][0] is 'l':
        acc = join_trees(repo, path[1][1] , path[0][1])

    return validate_path(
        repo=repo,
        path=[('', acc)] + path[2:],
        root=root,
    )

def cache_audit_paths(repo: git.Repository, log: git.Oid) -> git.Oid:
    """build a tree containing sparse checkout filter specs for each leaf and it's audit path"""
    leaves = get_leaves(repo, log)
    for i in range(len(leaves)):
        chain = path(repo, i, leaves)
        assert validate_path(repo, [('l' if i % 2 == 0 else 'r', leaves[i])] + chain, log)

# --- testing ---

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    print(d)
    repo = git.init_repository(d, bare=True)

    builds = [store_leaf(repo, store_hash(), nar_hash()) for _ in range(1,8)]
    log = merkleise(repo, builds)
    assert builds == get_leaves(repo, log)

    cache_audit_paths(repo, log)
