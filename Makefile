name           = guesti
version       := $(shell sed -ne "0,/^v\([[:digit:].]\+\).*/ s//\1/p" ChangeLog)
spec           = guesti.spec
specin         = pkg/rpm/guesti.spec.in

#release: docs
#	python setup.py sdist register upload
.PHONY: docs srpm
all: build docs

build:
	python setup.py build

docs:
	python setup.py build_sphinx

install:
	python setup.py install -O1 --skip-build --root $DESTDIR

clean:
	rm -rf build dist docs/build
	rm -f MANIFEST *.log demos/*.log
	find guesti/ -name '*.pyc' -delete
	rm -f test.log guesti.spec *.rpm
	rm -rf guesti.egg-info

pep8:
	find guesti/ -type f -name '*.py' -exec autopep8 -i --max-line-length=180 {} \;
	find tools/  -type f              -exec autopep8 -i --max-line-length=180 {} \;

spec:
	sed -e "/@DESCRIPTION@/ {r DESCRIPTION" -e "d;}" -e "s/@VERSION@/${version}/" ${specin} >${spec}

srpm: spec
	git archive -9 --format=tar.gz --prefix=${name}-${version}/ --output=${name}-${version}.tar.gz master
	rpmbuild -D '%_sourcedir ./' -D '%_srcrpmdir ./' --rmsource -bs ${spec}

test:
	python ./test.py
