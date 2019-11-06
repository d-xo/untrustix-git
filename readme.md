# untrustix-git

## TODO:

- do consistency proofs require content or only hash of content?
- handle updating an existing store path with a new build result
- optimum sharding depth (tradeoff between inclusion / consistency proof size?)

## Repo Layout

Build results are stored in a `results` subfolder. Results are stored in a hash tree, keyed by their
store hash, and sharded into subdirectories (e.g. the expected contents of the store path identified
by `zzlfqv4p4hf55saim00zc9vvqj08nxjb` would be written to a file at `zz/lf/qv/4p/4h/f55saim00zc9vvqj08nxjb`).
Multiple build results are allowed per store path (to allow for legitimately unreproducible builds).
The sharding allows for the construction of compact proofs of:

- `inclusion`: a given build result is included in a given hash tree
- `consistency`: a given hash tree is append only relative to an older version

The other top level folder is `filters`. Each file in this directory is a git filter spec that
allows clients to perform a partial fetch containing only a single build result and it's associated
inclusion proof. This is required as the current git partial fetch protocol will by default return
all objects reffered to by a requested object.

## Proofs

### Inclusion

The inclusion proof is the familiar merkle branch proof. Given a leaf node and the branch from the
root to the leaf, the verifier can combine the leaf with the provided intermediate hashes and
confirm that they produce the expected root hash. This assumes that the client has obtained
knowledge of the root hash through some trusted side channel.

### Consistency

This proof assumes that only a single new leaf has been added to the tree. The verifier knows the
root hash of the old tree and the new tree. The prover provides:

1. A full branch in the old tree to the leaf where the new content will be inserted.
1. The new content

The verifier does the following:

1. Verifies that the branch in the old tree is valid
1. Recomputes the branch with the new content added and verifies that it results in the new root hash

This works because the branch in the old tree is a commitment to the state of the entire tree. If we
reuse the unchanged hashes from the old branch while computing the new root hash, then we can be
sure that the only change to the tree was the addition of the new content.

If each new build result is added as a new commit, then the consistency proof can be written to the
commit message.

## Client Protocol

Log followers are lightweight and need store only the most recent commit object (trees / blobs are
not required) for logs they are interested in. The number of operations required to lookup a build
is constant as the number of build results increases.

### Syncronisation

Clients start from a known good commit, and pull newer commits in order from the oldest to the
newest. As they receive new commits, they verify the consistency proofs. Once a newer commit has
been verified, all older commits can be discarded. This operation is linear with the number of
commits.

### Lookup

Clients make a single fetch request to the log using the filter spec for the store path they are
interested in to fetch only the build results and associated inclusion proof. They then verify the
inclusion proof. Once a result is verified, it's inclusion proof can be discarded. Old build results
can also be discarded.

