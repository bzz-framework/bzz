release:
	@grunt build
	@cp -r dist/index.html .
	@cp -r dist/scripts .
	@cp -r dist/styles .
	@cp -r dist/images .
	@cp -r dist/robots.txt .
