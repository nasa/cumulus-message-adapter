clean:
	rm -rf dist
	rm -rf dist_package
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

packaged_runtime: requirements
	cp __main__.py ./dist/
	pip install pyinstaller
	pyinstaller --distpath dist_package --clean -F -n cma ./dist/__main__.py

cumulus-message-adapter.zip: requirements packaged_runtime
	cp __main__.py ./dist/
	cp -R message_adapter ./dist/
	cp ./dist_package/cma ./dist/
	(cd dist && zip -r -9 ../cumulus-message-adapter.zip .)
