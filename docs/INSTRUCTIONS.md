## how to run:

**perft testing / benchmarking**: `clang++ -std=c++20 -O3 main.cpp -o main \
-I/opt/homebrew/include \
-L/opt/homebrew/lib \
-lraylib \
-framework IOKit \
-framework Cocoa \
-framework OpenGL`

i need the homebrew flags or else it wont detect raylib

**debug**: `clang++ -std=c++20 -g main.cpp -o main \
-I/opt/homebrew/include \
-L/opt/homebrew/lib \
-lraylib \
-framework IOKit \
-framework Cocoa \
-framework OpenGL`

**release**: `clang++ -std=c++20 -O3 -DNDEBUG main.cpp -o main \
-I/opt/homebrew/include \
-L/opt/homebrew/lib \
-lraylib \
-framework IOKit \
-framework Cocoa \
-framework OpenGL`

**emcc**: `emcc main.cpp -o index.html \                                                  
    -I/opt/homebrew/include \
    -L./raylib-5.0_webassembly/lib -lraylib \
    -s USE_GLFW=3 \
    -s ASYNCIFY \
    -DPLATFORM_WEB \
    --preload-file assets`