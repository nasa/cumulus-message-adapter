clean:
	rm -rf dist
	rm -f cumulus-message-adapter.zip

dist:
	mkdir -p dist

requirements: dist requirements.txt
	pip install -r requirements.txt --target ./dist/
	find ./dist -type d -name '__pycache__' | xargs rm -rf
	find ./dist/botocore/data -mindepth 1 -maxdepth 1 -type d |\
		egrep -v '(stepfunctions|s3)' |\
		xargs rm -rf
	rm -rf dist/docutils

cumulus-message-adapter.zip: requirements
	cp __main__.py ./dist/
	cp -R message_adapter ./dist/
	(cd dist && zip -r -9 ../cumulus-message-adapter.zip .)
