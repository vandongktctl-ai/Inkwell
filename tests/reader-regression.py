#!/usr/bin/env python3
"""Run reader regression checks on a Linux host with cc and sanitizers.
Usage: python3 tests/reader-regression.py
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FIXTURE = r'''"""Protocol fixture; page pixels identify their document, page, and font size."""
import sys
w, h, em, doc = 32, 142, 30, 0
for line in sys.stdin:
    f = line.rstrip('\n').split('\t')
    if f[0] == 'open':
        w, h, em = map(int, f[2:5])
        doc = 100 if 'second' in f[1] else 0
        print('ok\t10\t1\tTest book\tAuthor', flush=True)
    elif f[0] == 'layout':
        w, h, em = map(int, f[1:4])
        print('ok\t10', flush=True)
    elif f[0] == 'render':
        page = int(f[1])
        with open(f[3], 'wb') as out:
            out.write(f'P5\n{w} {h}\n255\n'.encode())
            out.write(bytes([(doc + em + page) % 256]) * w * h)
        with open('/tmp/inkwell-test-renders', 'a') as log:
            log.write(f'{doc} {em} {page}\n')
        print(f'ok\t{w}\t{h}', flush=True)
    else:
        print('err\tunsupported fixture command', flush=True)
'''
C_SOURCE = r'''/* Host regression checks: renderer/cache boundaries, row clipping and exact
 * strip-position saves. No Kindle hardware or copyrighted book is needed. */
#define STATE_DIR "/tmp/inkwell-reader-regression"
#define main inkwell_books_main
#include "../src/ui/books.c"
#undef main
#include <assert.h>

static int render_count(void) {
    FILE *f = fopen("/tmp/inkwell-test-renders", "r");
    int n = 0, c;
    if (!f) return 0;
    while ((c = fgetc(f)) != EOF) if (c == '\n') n++;
    fclose(f); return n;
}
int main(void) {
    unlink("/tmp/inkwell-test-renders");
    W = PITCH = 32; H = 200;
    fb = calloc((size_t)PITCH, H);
    assert(fb);
    signal(SIGPIPE, SIG_IGN);
    helper_start();
    assert(open_book("/tmp/first.epub") == 0);
    bk.page = 0; assert(prepare() == 0 && pg.px[0] == 30);
    bk.page = 1; assert(prepare() == 0 && pg.px[0] == 31);
    int count = render_count();
    bk.page = 0; assert(prepare() == 0 && pg.px[0] == 30);
    bk.page = 1; assert(prepare() == 0 && pg.px[0] == 31);
    assert(render_count() == count); /* revisit without asking MuPDF */
    relayout(4); assert(bk.em == 34);
    assert(prepare() == 0 && pg.px[0] == 35);
    assert(render_count() == count + 1); /* changed size cannot reuse pixels */
    assert(open_book("/tmp/second.epub") == 0);
    bk.page = 0; assert(prepare() == 0 && pg.px[0] == 130);
    assert(previous_page == -1); /* no pixels leak between books */

    bk.page = 4; bk.part = 2; bk.nparts = 5; bk.mode = 1;
    bk.nmarks = 1; bk.marks[0] = 7;
    save_state();
    book loaded = {0}; load_state(bk.path, &loaded);
    assert(loaded.page == 4 && loaded.part == 2 && loaded.nparts == 5);
    assert(loaded.mode == 1 && loaded.nmarks == 1 && loaded.marks[0] == 7);
    assert(title_contains("Alice in Wonderland", "WONDER"));
    assert(!title_contains("Alice", "Alice in Wonderland"));
    assert(title_contains("Alice", ""));

    /* Exercise fast row copies against the original per-pixel clipping rule,
     * including oversize rectangles and negative source/destination offsets. */
    unsigned char px[48]; for (int i = 0; i < 48; i++) px[i] = i;
    image test = {8, 6, px};
    unsigned char expected[32 * 200];
    for (int sx = -9; sx <= 9; sx += 3) for (int sy = -7; sy <= 7; sy += 2)
    for (int dx = -10; dx <= 35; dx += 5) for (int dy = -8; dy <= VIEW_H + 8; dy += 13) {
        memset(fb, 255, sizeof expected); memset(expected, 255, sizeof expected);
        for (int j = 0; j < 12; j++) for (int i = 0; i < 20; i++) {
            int x = dx + i, y = dy + j, ix = sx + i, iy = sy + j;
            if (x >= 0 && x < W && y >= 0 && y < VIEW_H && ix >= 0 && ix < test.w && iy >= 0 && iy < test.h)
                expected[y * PITCH + x] = px[iy * test.w + ix];
        }
        blit(&test, sx, sy, 20, 12, dx, dy);
        assert(memcmp(fb, expected, sizeof expected) == 0);
    }
    /* A truncated PGM must leave the last valid image intact. */
    FILE *bad = fopen("/tmp/inkwell-bad.pgm", "wb");
    fputs("P5\n8 6\n255\nshort", bad); fclose(bad);
    unsigned char *before = pg.px;
    assert(read_pgm("/tmp/inkwell-bad.pgm", &pg) == -1 && pg.px == before);
    helper_stop(); clear_page_cache(); free(pg.px); free(fb);
    puts("PASS: cache reuse/invalidation, saved PDF part, search, clipping and truncated images");
}
'''


HOME_SOURCE = r'''
#define READER_STATE_DIR "STATE_DIRECTORY"
#define main inkwell_home_main
#include "HOME_SOURCE_PATH"
#undef main
#include <assert.h>
int main(void) {
    W = PITCH = 1072; H = 1448;
    for (napps = 0; napps <= 16; napps++) {
        layout();
        for (app_page = 0; app_page < (napps + 8) / 9; app_page++) {
            for (int i = app_page * 9; i < napps && i < (app_page + 1) * 9; i++) {
                rect r = apps[i].r;
                assert(app_at(r.x + r.w / 2, r.y + r.h / 2) == i);
                assert(r.y + r.h <= GRID_BOTTOM);
            }
            assert(app_at(0, 0) == -1);
        }
    }
    /* A newer state pointing at a removed book cannot replace a valid one. */
    char doc[1024], state[1024];
    snprintf(doc, sizeof doc, "%s/book's name.epub", READER_STATE_DIR);
    FILE *f = fopen(doc, "w"); assert(f); fclose(f);
    snprintf(state, sizeof state, "%s/one.txt", READER_STATE_DIR);
    f = fopen(state, "w"); assert(f);
    fprintf(f, "path %s\ntitle Current book\nopened 100\npage 2\npages 10\n", doc); fclose(f);
    snprintf(state, sizeof state, "%s/two.txt", READER_STATE_DIR);
    f = fopen(state, "w"); assert(f);
    fputs("path /missing/book.epub\ntitle Removed\nopened 200\n", f); fclose(f);
    load_recent();
    assert(!strcmp(recent_path, doc) && !strcmp(recent_title, "Current book"));
    assert(recent_page == 2 && recent_pages == 10);
    unlink(doc); load_recent(); assert(!recent_path[0]);
    puts("PASS: 0-16 app pagination, correct touch targets, and deleted-book fallback");
}
'''

def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="inkwell-reader-") as tmp:
        work = Path(tmp)
        # All state and renderer output live in a private temporary directory.
        state = work / "state"
        state.mkdir()
        source = C_SOURCE.replace('"/tmp/inkwell-reader-regression"', '"' + str(state) + '"')
        source = source.replace('/tmp/inkwell-test-renders', str(work / 'renders'))
        source = source.replace('/tmp/inkwell-bad.pgm', str(work / 'bad.pgm'))
        source = source.replace('../src/ui/books.c', str(root / 'src/ui/books.c'))
        fixture = FIXTURE.replace('/tmp/inkwell-test-renders', str(work / 'renders'))
        (work / "test.c").write_text(source)
        tool = work / "mutool"
        tool.write_text("#!" + sys.executable + "\n" + fixture)
        tool.chmod(0o700)
        subprocess.run([shutil.which("cc") or "cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-I" + str(root / "third_party/stb"), "-Wno-unused-function", str(work / "test.c"),
                        "-o", str(work / "reader-test"), "-lm"], check=True)
        home = HOME_SOURCE.replace("STATE_DIRECTORY", str(state)).replace("HOME_SOURCE_PATH", str(root / "src/ui/home.c"))
        (work / "home-test.c").write_text(home)
        subprocess.run([shutil.which("cc") or "cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-I" + str(root / "third_party/stb"), "-Wno-unused-function", str(work / "home-test.c"),
                        "-o", str(work / "home-test"), "-lm"], check=True)
        env = dict(os.environ, PATH=str(work) + os.pathsep + os.environ["PATH"], ASAN_OPTIONS="detect_leaks=0")
        subprocess.run([str(work / "reader-test")], env=env, check=True, timeout=60)
        subprocess.run([str(work / "home-test")], env=env, check=True, timeout=60)

if __name__ == "__main__":
    main()
