#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

#define UNIT_TEST
#include "../main.cpp"

void expectFENLoads(const std::string &fen, Board &board)
{
    bool loaded = loadFEN(board, fen);

    if (!loaded)
    {
        std::cerr << "[FAIL] Could not load FEN: " << fen << '\n';
    }

    assert(loaded);
}

bool boardsEqual(const Board &a, const Board &b)
{
    for (int color = 0; color < 2; ++color)
    {
        for (int piece = 0; piece < 6; ++piece)
        {
            if (a.pieces[color][piece] != b.pieces[color][piece])
                return false;
        }
    }

    return a.whitePieces == b.whitePieces &&
           a.blackPieces == b.blackPieces &&
           a.allPieces == b.allPieces &&
           a.sideToMove == b.sideToMove &&
           a.castlingRights == b.castlingRights &&
           a.enPassantSquares == b.enPassantSquares &&
           a.enPassantDest == b.enPassantDest &&
           a.halfmoveClock == b.halfmoveClock &&
           a.fullMoveNumber == b.fullMoveNumber;
}

void expectPerft(
    const std::string &name,
    const std::string &fen,
    int depth,
    uint64_t expected)
{
    Board board;
    expectFENLoads(fen, board);

    uint64_t actual = perft(board, depth);

    if (actual != expected)
    {
        std::cerr
            << "[FAIL] " << name
            << " depth " << depth
            << ": expected " << expected
            << ", got " << actual
            << '\n';
    }
    else
    {
        std::cout
            << "[PASS] " << name
            << " depth " << depth
            << " = " << actual
            << '\n';
    }

    assert(actual == expected);
}

void clearBoard(Board &board)
{
    for (int color = 0; color < 2; ++color)
    {
        for (int piece = 0; piece < 6; ++piece)
        {
            board.pieces[color][piece] = 0ULL;
        }
    }

    board.whitePieces = 0ULL;
    board.blackPieces = 0ULL;
    board.allPieces = 0ULL;

    board.sideToMove = White;
    board.castlingRights = 0;
    board.enPassantSquares = 0ULL;
    board.enPassantDest = -1;
    board.halfmoveClock = 0;
    board.fullMoveNumber = 1;
    board.positionHistory.clear();

    board.updateOccupancy();
}

void placePiece(
    Board &board,
    myColor color,
    PieceTypes piece,
    int square)
{
    assert(square >= 0 && square < 64);
    board.pieces[color][piece] |= 1ULL << square;
}

void finishBoardSetup(Board &board)
{
    board.updateOccupancy();
}

void testKingVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);  // e1
    placePiece(board, Black, King, 60); // e8

    finishBoardSetup(board);

    assert(isInsufficientMaterial(board));
}

void testWhiteBishopVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);   // e1
    placePiece(board, White, Bishop, 2); // c1
    placePiece(board, Black, King, 60);  // e8

    finishBoardSetup(board);

    assert(isInsufficientMaterial(board));
}

void testBlackBishopVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);    // e1
    placePiece(board, Black, King, 60);   // e8
    placePiece(board, Black, Bishop, 58); // c8

    finishBoardSetup(board);

    assert(isInsufficientMaterial(board));
}

void testWhiteKnightVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);   // e1
    placePiece(board, White, Knight, 6); // g1
    placePiece(board, Black, King, 60);  // e8

    finishBoardSetup(board);

    assert(isInsufficientMaterial(board));
}

void testBlackKnightVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);    // e1
    placePiece(board, Black, King, 60);   // e8
    placePiece(board, Black, Knight, 62); // g8

    finishBoardSetup(board);

    assert(isInsufficientMaterial(board));
}

void testRookVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);  // e1
    placePiece(board, White, Rook, 0);  // a1
    placePiece(board, Black, King, 60); // e8

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testQueenVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);  // e1
    placePiece(board, White, Queen, 3); // d1
    placePiece(board, Black, King, 60); // e8

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testPawnVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);  // e1
    placePiece(board, White, Pawn, 12); // e2
    placePiece(board, Black, King, 60); // e8

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testSameColoredBishops()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);    // e1
    placePiece(board, White, Bishop, 2);  // c1, dark square
    placePiece(board, Black, King, 60);   // e8
    placePiece(board, Black, Bishop, 61); // f8, dark square

    finishBoardSetup(board);

    assert(isInsufficientMaterial(board));
}

void testOppositeColoredBishops()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);    // e1
    placePiece(board, White, Bishop, 2);  // c1, dark square
    placePiece(board, Black, King, 60);   // e8
    placePiece(board, Black, Bishop, 58); // c8, light square

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testBishopVsKnight()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);
    placePiece(board, White, Bishop, 2);
    placePiece(board, Black, King, 60);
    placePiece(board, Black, Knight, 62);

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testKnightVsKnight()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);
    placePiece(board, White, Knight, 1);
    placePiece(board, Black, King, 60);
    placePiece(board, Black, Knight, 62);

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testTwoKnightsVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);
    placePiece(board, White, Knight, 1);
    placePiece(board, White, Knight, 6);
    placePiece(board, Black, King, 60);

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testBishopAndKnightVsKing()
{
    Board board;
    clearBoard(board);

    placePiece(board, White, King, 4);
    placePiece(board, White, Bishop, 2);
    placePiece(board, White, Knight, 6);
    placePiece(board, Black, King, 60);

    finishBoardSetup(board);

    assert(!isInsufficientMaterial(board));
}

void testStartingPositionIsNotInsufficient()
{
    Board board;

    assert(!isInsufficientMaterial(board));
}

void testStartingPositionFEN()
{
    Board board;

    expectFENLoads(
        "rnbqkbnr/pppppppp/8/8/8/8/"
        "PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        board);

    assert(__builtin_popcountll(board.whitePieces) == 16);
    assert(__builtin_popcountll(board.blackPieces) == 16);
    assert(__builtin_popcountll(board.allPieces) == 32);

    assert(__builtin_popcountll(board.pieces[White][Pawn]) == 8);
    assert(__builtin_popcountll(board.pieces[Black][Pawn]) == 8);

    assert(board.pieces[White][King] == (1ULL << 4));  // e1
    assert(board.pieces[Black][King] == (1ULL << 60)); // e8

    assert(board.sideToMove == White);

    assert(board.castlingRights ==
           (WhiteKingSide |
            WhiteQueenSide |
            BlackKingSide |
            BlackQueenSide));

    assert(board.enPassantDest == -1);
    assert(board.enPassantSquares == 0ULL);
    assert(board.halfmoveClock == 0);
    assert(board.fullMoveNumber == 1);
}

void testEmptyBoardFEN()
{
    Board board;

    expectFENLoads(
        "8/8/8/8/8/8/8/8 b - - 25 73",
        board);

    assert(board.allPieces == 0ULL);
    assert(board.whitePieces == 0ULL);
    assert(board.blackPieces == 0ULL);

    assert(board.sideToMove == Black);
    assert(board.castlingRights == 0);
    assert(board.enPassantDest == -1);
    assert(board.enPassantSquares == 0ULL);
    assert(board.halfmoveClock == 25);
    assert(board.fullMoveNumber == 73);
}

void testPiecePlacementFEN()
{
    Board board;

    expectFENLoads(
        "4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1",
        board);

    assert(board.pieces[Black][King] == (1ULL << 60));  // e8
    assert(board.pieces[Black][Queen] == (1ULL << 35)); // d5
    assert(board.pieces[White][Pawn] == (1ULL << 28));  // e4
    assert(board.pieces[White][King] == (1ULL << 4));   // e1

    assert(__builtin_popcountll(board.allPieces) == 4);
}

void testPartialCastlingRightsFEN()
{
    Board board;

    expectFENLoads(
        "r3k2r/8/8/8/8/8/8/R3K2R b Kq - 0 1",
        board);

    assert(board.sideToMove == Black);
    assert(board.castlingRights & WhiteKingSide);
    assert(board.castlingRights & BlackQueenSide);

    assert(!(board.castlingRights & WhiteQueenSide));
    assert(!(board.castlingRights & BlackKingSide));
}

void testWhiteEnPassantFEN()
{
    Board board;

    expectFENLoads(
        "4k3/8/8/3Pp3/8/8/8/4K3 w - e6 0 1",
        board);

    assert(board.sideToMove == White);
    assert(board.enPassantDest == 44);              // e6
    assert(board.enPassantSquares == (1ULL << 35)); // d5
}

void testBlackEnPassantFEN()
{
    Board board;

    expectFENLoads(
        "4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 1",
        board);

    assert(board.sideToMove == Black);
    assert(board.enPassantDest == 20);              // e3
    assert(board.enPassantSquares == (1ULL << 27)); // d4
}

void testInvalidFENs()
{
    Board board;

    assert(!loadFEN(board, ""));
    assert(!loadFEN(board, "invalid"));
    assert(!loadFEN(board, "8/8/8/8/8/8/8/9 w - - 0 1"));
    assert(!loadFEN(board, "8/8/8/8/8/8/8/8 x - - 0 1"));
    assert(!loadFEN(board, "8/8/8/8/8/8/8/8 w X - 0 1"));
    assert(!loadFEN(board, "8/8/8/8/8/8/8/8 w - z9 0 1"));
}

void testStartingPositionLegalMoveCount()
{
    Board board;

    assert(loadFEN(
        board,
        "rnbqkbnr/pppppppp/8/8/8/8/"
        "PPPPPPPP/RNBQKBNR w KQkq - 0 1"));

    uint64_t nodes = perft(board, 1);

    std::cout << "Starting-position legal moves: " << nodes << '\n';

    assert(nodes == 20);
}

void testKiwipetePerft()
{
    const std::string fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1";

    expectPerft("Kiwipete", fen, 1, 48);
    expectPerft("Kiwipete", fen, 2, 2039);
    expectPerft("Kiwipete", fen, 3, 97862);
}

void testPerftPositionThree()
{
    const std::string fen =
        "8/2p5/3p4/KP5r/1R3p1k/"
        "8/4P1P1/8 w - - 0 1";

    expectPerft("Position 3", fen, 1, 14);
    expectPerft("Position 3", fen, 2, 191);
    expectPerft("Position 3", fen, 3, 2812);
    expectPerft("Position 3", fen, 4, 43238);
}

void testPromotionPerft()
{
    const std::string fen =
        "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1";

    expectPerft("Promotion position", fen, 1, 24);
    expectPerft("Promotion position", fen, 2, 496);
    expectPerft("Promotion position", fen, 3, 9483);
}

void testMakeUndoStartingMoves()
{
    Board original;

    assert(loadFEN(
        original,
        "rnbqkbnr/pppppppp/8/8/8/8/"
        "PPPPPPPP/RNBQKBNR w KQkq - 0 1"));

    movesList moves = generateMoves(original);
    int legalMoves = 0;

    for (int i = 0; i < moves.count; ++i)
    {
        // Fresh board for every attempted move.
        Board board = original;

        undoInfo undo;

        if (!makeMove(board, moves.moves[i], undo))
        {
            continue;
        }

        ++legalMoves;

        undoMove(board, moves.moves[i], undo);

        if (!boardsEqual(board, original))
        {
            int src = moves.moves[i] & 0x3F;
            int dest = (moves.moves[i] >> 6) & 0x3F;
            int flag = (moves.moves[i] >> 12) & 0xF;

            std::cerr
                << "[FAIL] Board not restored after move"
                << " src=" << src
                << " dest=" << dest
                << " flag=" << flag
                << '\n';

            assert(false);
        }
    }

    std::cout
        << "Generated moves: " << moves.count << '\n'
        << "Legal moves: " << legalMoves << '\n';

    assert(legalMoves == 20);

    std::cout << "[PASS] All starting moves restore correctly\n";
}

int main()
{
    knightLookup();
    kingLookup();
    initZobrist();

    std::cout << "Running FEN tests...\n";

    testStartingPositionFEN();
    testEmptyBoardFEN();
    testPiecePlacementFEN();
    testPartialCastlingRightsFEN();
    testWhiteEnPassantFEN();
    testBlackEnPassantFEN();
    testInvalidFENs();

    std::cout << "Running make/undo tests...\n";
    testStartingPositionLegalMoveCount();
    testMakeUndoStartingMoves();

    std::cout << "Running perft tests...\n";

    testKiwipetePerft();
    testPerftPositionThree();
    testPromotionPerft();

    std::cout << "\nAll chess-engine tests passed!\n";
    return 0;
}