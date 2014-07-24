setup:
	@npm install .
	@bower install

release:
	@grunt build
	@rm -rf index.html ./scripts ./styles ./images ./robots.txt
	@cp -r dist/index.html .
	@cp -r dist/scripts .
	@cp -r dist/styles .
	@cp -r dist/images .
	@cp -r dist/robots.txt .
