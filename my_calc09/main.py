
import argparse

def add(a, b):
    return a + b

def sub(a, b):
    return a - b


def main():
    parser = argparse.ArgumentParser(description="CLI calculator with add/subtract")

    parser.add_argument("operation", choices=["add", "sub"], help="Operation")
    parser.add_argument("a", type=float)
    parser.add_argument("b", type=float)

    args = parser.parse_args()

    if args.operation == "add":
        result = add(args.a, args.b)
    else:
        result = sub(args.a, args.b)

    print("Result:", result)


if __name__ == "__main__":
    main()
