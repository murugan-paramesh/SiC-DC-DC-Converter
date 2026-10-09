# Host build of the portable control core + SIL harness (gcc).  The C2000 target build uses
# hal/c2000 with Code Composer Studio / C2000Ware (not available in this environment).
CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c11 -Isrc -Ihal/sil
SRC = src/dab_control.c src/dab_comm.c hal/sil/plant.c sil/sil_main.c
all: sil/sil_test
sil/sil_test: $(SRC) src/dab_params.h
	$(CC) $(CFLAGS) -o $@ $(SRC) -lm
test: sil/sil_test
	./sil/sil_test
params:
	python3 tools/gen_params.py
clean:
	rm -f sil/sil_test sil/sil_results.csv
.PHONY: all test params clean
