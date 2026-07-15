#include <cstdint>
#include <iostream>
using namespace std;

uint64_t startingPawns = 0x000000000000FF00 & 0xff00ffffffffffff;

enum PieceTypes
{
    Pawn,
    Knight,
    Bishop,
    Rook,
    King,
    Queen
};

enum Color
{
    White = 0,
    Black = 1
};

class Board
{
public:
    uint64_t pieces[2][6];
    // {x, x, x, x, x, x}
    // {x, x, x, x, x, x}

    uint64_t whitePieces;
    uint64_t blackPieces;
    uint64_t allPieces;

    Color sideToMove;

    int castlingRights;
    int enPassantSquare;

    Board()
    {
        for (int c = 0; c < 2; ++c)
        {
            for (int p = 0; p < 6; ++p)
            {
                pieces[c][p] = 0ULL;
            }
        }

        pieces[White][Pawn] = 0x000000000000FF00;
        pieces[White][Rook] = 0x0000000000000081;
        pieces[White][Knight] = 0x0000000000000042;
        pieces[White][Bishop] = 0x0000000000000024;
        pieces[White][Queen] = 0x0000000000000008;
        pieces[White][King] = 0x0000000000000010;

        pieces[Black][Pawn] = 0x00FF000000000000;
        pieces[Black][Rook] = 0x8100000000000000;
        pieces[Black][Knight] = 0x4200000000000000;
        pieces[Black][Bishop] = 0x2400000000000000;
        pieces[Black][Queen] = 0x0800000000000000;
        pieces[Black][King] = 0x1000000000000000;

        updateOccupancy();
    }

    void updateOccupancy()
    {
        whitePieces = 0;
        blackPieces = 0;
        for (int i = 0; i < 6; ++i)
        {
            whitePieces |= pieces[White][i];
            blackPieces |= pieces[Black][i];
        }
        allPieces = whitePieces | blackPieces;
    }
};

struct movesList
{
    uint16_t moves[256];
    int count = 0;

    void addMove(uint16_t move)
    {
        moves[count] = move;
        ++count;
    }
};

int main()
{
    Board chessBoard;
};

movesList generateMoves(const Board &board)
{

    // uint16_t move: bits: 0-5 source, 6-11 destination, 12-13 promotion piece, 13-16 flags (en passsant, castle, double push)

    movesList moves;

    serializePawnMoves(board, moves);

    return moves;
}

void serializePawnMoves(const Board &board, movesList &list)
{

    uint64_t emptySquares = ~board.allPieces;

    if (board.sideToMove == White)
    {
        uint64_t rank4 = 0xff000000ULL;

        uint64_t wPawns = board.pieces[White][Pawn];

        uint64_t singlePushes = (wPawns << 8) & emptySquares;
        uint64_t doublePushes = (singlePushes << 8) & emptySquares & rank4;

        // Single Pushes
        while (singlePushes != 0)
        {
            int dest = __builtin_ctzll(singlePushes);
            int src = dest - 8;

            uint16_t move = src | (dest << 6);

            list.addMove(move);

            singlePushes &= (singlePushes - 1);
        }

        // Double Pushes
        while (doublePushes != 0)
        {
            int dest = __builtin_ctzll(doublePushes);
            int src = dest - 16;

            uint16_t flag = (1 << 14);
            uint16_t move = src | (dest << 6) | flag;

            list.addMove(move);

            doublePushes &= (doublePushes - 1);
        }

        // Captures
        uint64_t notFileH = 0x7F7F7F7F7F7F7F7F;
        uint64_t capturesLeft = (wPawns << 7) & board.blackPieces & notFileH;
        while (capturesLeft != 0)
        {
            int dest = __builtin_ctzll(capturesLeft);
            int src = dest - 7;

            uint16_t move = src | (dest << 6);

            list.addMove(move);

            capturesLeft &= (capturesLeft - 1);
        }

        uint64_t notFileA = 0xFEFEFEFEFEFEFEFE;
        uint64_t capturesRight = (wPawns << 9) & board.blackPieces & notFileA;
        while (capturesRight != 0)
        {
            int dest = __builtin_ctzll(capturesRight);
            int src = dest - 9;

            uint16_t move = src | (dest << 6);

            list.addMove(move);

            capturesRight &= (capturesRight - 1);
        }
    }
    else if (board.sideToMove == Black)
    {
        uint64_t rank5 = 0xff00000000ULL;
        uint64_t bPawns = board.pieces[Black][Pawn];

        uint64_t singlePushes = (bPawns >> 8) & emptySquares;
        uint64_t doublePushes = (singlePushes >> 8) & emptySquares & rank5;

        // Single Pushes
        while (singlePushes != 0)
        {
            int dest = __builtin_ctzll(singlePushes);
            int src = dest + 8;

            uint16_t move = src | (dest << 6);

            list.addMove(move);

            singlePushes &= (singlePushes - 1);
        }

        // Double Pushes
        while (doublePushes != 0)
        {
            int dest = __builtin_ctzll(doublePushes);
            int src = dest + 16;

            uint16_t flag = (1 << 14);
            uint16_t move = src | (dest << 6) | flag;

            list.addMove(move);

            doublePushes &= (doublePushes - 1);
        }

        uint64_t notFileH = 0x7F7F7F7F7F7F7F7F;
        uint64_t capturesLeft = (bPawns >> 9) & board.whitePieces & notFileH;
        while (capturesLeft != 0)
        {
            int dest = __builtin_ctzll(capturesLeft);
            int src = dest + 9;

            uint16_t move = src | (dest << 6);

            list.addMove(move);

            capturesLeft &= (capturesLeft - 1);
        }

        uint64_t notFileA = 0xFEFEFEFEFEFEFEFE;
        uint64_t capturesRight = (bPawns >> 7) & board.whitePieces & notFileA;
        while (capturesRight != 0)
        {
            int dest = __builtin_ctzll(capturesRight);
            int src = dest + 7;

            uint16_t move = src | (dest << 6);

            list.addMove(move);

            capturesRight &= (capturesRight - 1);
        }
    }
}

void printBoard(const Board &board)
{
    const char symbolsW[] = {'P', 'N', 'B', 'R', 'K', 'Q'};
    const char symbolsB[] = {'p', 'n', 'b', 'r', 'k', 'q'};

    std::cout << "\n  +-----------------+\n";

    for (int rank = 7; rank >= 0; --rank)
    {
        std::cout << (rank + 1) << " | ";

        for (int file = 0; file < 8; ++file)
        {
            int square = rank * 8 + file;
            uint64_t squareMask = 1ULL << square;
            char pieceChar = '.';

            bool pieceFound = false;
            for (int p = 0; p < 6; ++p)
            {
                if (board.whitePieces & squareMask)
                {
                    pieceChar = symbolsW[p];
                    pieceFound = true;
                    break;
                }
                if (board.blackPieces & squareMask)
                {
                    pieceChar = symbolsB[p];
                    pieceFound = true;
                    break;
                }
            }

            std::cout << pieceChar << ' ';
        }
        std::cout << "|\n";
    }
    std::cout << "  +-----------------+\n";
    std::cout << "    a b c d e f g h\n\n";
    std::cout << "Side to move: " << (board.sideToMove == White ? "White" : "Black");
}