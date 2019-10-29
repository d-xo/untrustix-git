types:
	nix-shell --pure --command "mypy --strict ./main.py"
run:
	nix-shell --pure --command ./main.py
