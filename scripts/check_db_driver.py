"""Check native DB driver loading without opening a database or reading secrets."""
import sys


def main():
    try:
        import psycopg
    except ImportError:
        print('PostgreSQL Python driver could not load (psycopg/libpq).', file=sys.stderr)
        print('This check runs before connecting to PostgreSQL; DATABASE_URL has not been tested.', file=sys.stderr)
        print('If Windows reports an application control block, ask the policy administrator to review', file=sys.stderr)
        print('Microsoft-Windows-CodeIntegrity/Operational events and approve a supported driver.', file=sys.stderr)
        print('Diagnostic command: .venv\\Scripts\\python.exe -c "import psycopg"', file=sys.stderr)
        print('See README.md: Windows DB driver startup errors.', file=sys.stderr)
        return 1
    print(f'PostgreSQL driver loaded: psycopg {psycopg.__version__}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
