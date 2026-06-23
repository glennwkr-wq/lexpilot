import argparse

from app.services.federal_law.import_ruslawod import import_ruslawod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--create-indexes", action="store_true")

    args = parser.parse_args()

    result = import_ruslawod(
        limit_files=args.limit_files,
        batch_size=args.batch_size,
        create_indexes=args.create_indexes,
    )

    print(result)


if __name__ == "__main__":
    main()