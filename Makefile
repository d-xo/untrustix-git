types:
	mypy --strict *.py
fmt:
	black -t py37 *.py
builder:
	./builder.py
