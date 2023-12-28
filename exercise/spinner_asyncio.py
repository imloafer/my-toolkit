import itertools
import asyncio


async def spin(msg: str) -> None:
    for char in itertools.cycle(r'\|/-'):
        status = f'\r{char} {msg}'
        print(status, end='', flush=True)
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            break
    blanks = ' ' * len(status)
    print(f'\r{blanks}\r', end='')


async def slow() -> int:
    await asyncio.sleep(5)
    return 42


async def supervisor():
    spinner = asyncio.create_task((spin('thinking!')))
    print(f'spinner object: {spinner}')
    result = await slow()
    spinner.cancel()
    return result


def main():
    result = asyncio.run(supervisor())
    print(f'Answer: {result}')


if __name__ == '__main__':
    main()