SWIFTC ?= xcrun swiftc
TARGET := vm-studio-lossless
SOURCE := vm-studio-lossless.swift
WRAPPER := vm-studio

.PHONY: all clean test

all: $(TARGET) $(WRAPPER)
	chmod +x $(WRAPPER)

$(TARGET): $(SOURCE)
	@set -eu; \
	build_tmp=$$(mktemp "./.vm-studio-lossless.XXXXXX"); \
	trap 'rm -f "$$build_tmp"' 0; \
	trap 'exit 1' HUP INT TERM; \
	$(SWIFTC) \
		-parse-as-library \
		$(SOURCE) \
		-framework AVFoundation \
		-framework Cinematic \
		-framework AudioToolbox \
		-o "$$build_tmp"; \
	chmod +x "$$build_tmp"; \
	mv -f "$$build_tmp" $(TARGET)

clean:
	rm -f $(TARGET)

test:
	bash -n $(WRAPPER)
	python3 -m unittest discover -s tests -v
