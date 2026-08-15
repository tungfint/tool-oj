import os
import shutil
import zipfile


PROBLEM_CODE = "tonghaiso"
TEST_DIR = PROBLEM_CODE
ZIP_NAME = f"{PROBLEM_CODE}.zip"


def solve(a: int, b: int) -> int:
    return a + b


def write_case(index: int, a: int, b: int) -> None:
    name = f"{index:02d}"
    with open(os.path.join(TEST_DIR, f"{name}.inp"), "w", encoding="utf-8") as f:
        f.write(f"{a} {b}\n")
    with open(os.path.join(TEST_DIR, f"{name}.out"), "w", encoding="utf-8") as f:
        f.write(f"{solve(a, b)}\n")


def main() -> None:
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR, exist_ok=True)

    tests = [
        (1, 2),
        (0, 0),
        (-5, 7),
        (10**9, 10**9),
        (-10**9, -10**9),
    ]
    for index, (a, b) in enumerate(tests, 1):
        write_case(index, a, b)

    if os.path.exists(ZIP_NAME):
        os.remove(ZIP_NAME)
    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(os.listdir(TEST_DIR)):
            archive.write(os.path.join(TEST_DIR, filename), filename)
    print(f"Created {ZIP_NAME} with {len(tests)} tests")


if __name__ == "__main__":
    main()

