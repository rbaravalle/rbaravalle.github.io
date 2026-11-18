"""Conway's Game of Life on a 10x10 grid (non-wrapping), starting with a glider."""

SIZE = 10


def make_grid(alive):
    grid = [[0] * SIZE for _ in range(SIZE)]
    for r, c in alive:
        grid[r][c] = 1
    return grid


def step(grid):
    new = [[0] * SIZE for _ in range(SIZE)]
    for r in range(SIZE):
        for c in range(SIZE):
            n = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < SIZE and 0 <= cc < SIZE:
                        n += grid[rr][cc]
            if grid[r][c]:
                new[r][c] = 1 if n in (2, 3) else 0
            else:
                new[r][c] = 1 if n == 3 else 0
    return new


def live_cells(grid):
    return {(r, c) for r in range(SIZE) for c in range(SIZE) if grid[r][c]}


def show(grid, gen):
    print(f"Generation {gen}:")
    for row in grid:
        print(" ".join("#" if x else "." for x in row))
    print()


def main():
    # Standard glider in the top-left corner
    start = {(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)}
    grid = make_grid(start)
    show(grid, 0)
    for gen in range(1, 5):
        grid = step(grid)
        show(grid, gen)

    expected = {(r + 1, c + 1) for r, c in start}
    final = live_cells(grid)
    if final == expected:
        print("CHECK PASSED: glider moved one cell diagonally (+1 row, +1 col) after 4 generations.")
    else:
        print("CHECK FAILED")
        print("Expected:", sorted(expected))
        print("Got:     ", sorted(final))


if __name__ == "__main__":
    main()
