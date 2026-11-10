CC = gcc
CFLAGS = -Wall -Wextra -O2 -g
TARGET = nat64
SRCS = src/nat64.c

all: $(TARGET)

$(TARGET): $(SRCS) src/nat64.h
	$(CC) $(CFLAGS) -o $(TARGET) $(SRCS)

clean:
	rm -f $(TARGET)
