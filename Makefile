types:
	nix-shell --pure --command "mypy --strict *.py"
fmt:
	nix-shell --pure --command "black -t py37 *.py"
builder:
	nix-shell --pure --command ./builder.py
