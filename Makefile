# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com
#

# lists all available targets
list:
	@sh -c "$(MAKE) -p no_targets__ | awk -F':' '/^[a-zA-Z0-9][^\$$#\/\\t=]*:([^=]|$$)/ {split(\$$1,A,/ /);for(i in A)print A[i]}' | grep -v '__\$$' | grep -v 'make\[1\]' | grep -v 'Makefile' | sort"
# required for list
no_targets__:

# install all dependencies (do not forget to create a virtualenv first)
setup:
	# ujson can fail in pypy, we use json if ujson not installed
	@-pip install -U ujson
	@pip install -U -e .\[tests\]

# test your application (tests in the tests/ directory)
test: test_dependencies unit doctest

test_dependencies: mongo_test drop_test

unit:
	@coverage run --branch `which nosetests` -vv --with-yanc --logging-level=WARNING -s tests/
	@coverage report -m --fail-under=70

focus:
	@coverage run --branch `which nosetests` -vv --with-yanc --logging-level=WARNING --with-focus -s tests/

failed:
	@coverage run --branch `which nosetests` -vv --with-yanc --logging-level=WARNING --failed -s tests/

doctest:
	@cd docs && make doctest

# show coverage in html format
coverage-html: unit
	@coverage html -d cover

# get a mongodb instance up (localhost:3333)
mongo: kill_mongo
	@mkdir -p /tmp/bzz/mongodata && mongod --dbpath /tmp/bzz/mongodata --logpath /tmp/bzz/mongolog --port 3333 --quiet &

# kill this mongodb instance (localhost:3333)
kill_mongo:
	@-ps aux | egrep -i 'mongod.+3333' | egrep -v egrep | awk '{ print $$2 }' | xargs kill -9

# clear all data in this mongodb instance (localhost: 3333)
clear_mongo:
	@rm -rf /tmp/bzz && mkdir -p /tmp/bzz/mongodata

# get a mongodb instance up for your unit tests (localhost:3334)
mongo_test: kill_mongo_test
	@rm -rf /tmp/test-pkg/mongotestdata && mkdir -p /tmp/test-pkg/mongotestdata
	@mongod --dbpath /tmp/test-pkg/mongotestdata --logpath /tmp/test-pkg/mongotestlog --port 3334 --quiet --fork
	@echo 'waiting for mongo...'
	@until mongo --port 3334 --eval "quit()"; do echo ;sleep 0.25; done > /dev/null 2> /dev/null

# kill the test mongodb instance (localhost: 3334)
kill_mongo_test:
	@-ps aux | egrep -i 'mongod.+3334' | egrep -v egrep | awk '{ print $$2 }' | xargs kill -9

tox:
	@tox

update-docs:
	@cd docs && make html

open-docs:
	@cd docs && open _build/html/index.html

publish:
	@python setup.py sdist upload

drop_test:
	@mysql -u root -e "DROP DATABASE IF EXISTS test_bzz; CREATE DATABASE IF NOT EXISTS test_bzz"
	@echo "DB RECREATED"
