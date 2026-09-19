SWIFTC ?= xcrun swiftc
TARGET := vm-studio-lossless
SOURCE := vm-studio-lossless.swift
WRAPPER := vm-studio

.PHONY: all clean

all: $(TARGET) $(WRAPPER)
	chmod +x $(WRAPPER)

$(TARGET): $(SOURCE)
	$(SWIFTC) \
		-parse-as-library \
		$(SOURCE) \
		-framework AVFoundation \
		-framework Cinematic \
		-framework AudioToolbox \
		-o $(TARGET)

clean:
	rm -f $(TARGET)
