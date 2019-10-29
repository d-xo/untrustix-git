# repo layout

```
/log -> append only merkleised log of build results
/results -> flat directory of filter specs for merkle brances for each output
/audit -> flat directory of filter specs for merkle audit proofs for each commit
```

- stateful builders (can maybe prune old build results?)
- stateless clients
- O(1) lookup

TODO:

- generate test data (1000 builds)
- build tree
- build inclusion proofs
- build audit proofs

- directory is structured as a merkle tree with a file name1
- filter specs for the inclusion and append only proofs are written for each commit
- clients request objects using the sparse checkout filter


