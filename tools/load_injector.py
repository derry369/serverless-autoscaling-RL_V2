import asyncio
import aiohttp
import csv
from datetime import datetime


async def single_request(session: aiohttp.ClientSession, url: str):
    start = datetime.utcnow()
    try:
        async with session.get(url) as resp:
            await resp.read()
            status = resp.status
    except Exception as e:
        status = f"ERR:{type(e).__name__}"
    end = datetime.utcnow()
    # Minimal logging to stdout; you can redirect to a file if needed.
    print(f"{start.isoformat()}Z -> {end.isoformat()}Z status={status}")


async def fire_minute(session: aiohttp.ClientSession, url: str, invocations_per_minute: float):
    """
    Fire approximately invocations_per_minute requests during one logical minute.
    Requests are spread evenly over the minute with simple fixed spacing.[web:1124][web:1126]
    """
    if invocations_per_minute <= 0:
        # No load this minute: just wait out the minute.
        await asyncio.sleep(60.0)
        return

    # Number of requests this minute (integer).
    num_requests = int(invocations_per_minute)

    if num_requests <= 0:
        await asyncio.sleep(60.0)
        return

    # Time gap between requests in seconds.
    interval = 60.0 / num_requests

    tasks = []
    for i in range(num_requests):
        # Schedule requests spaced by 'interval' seconds.
        tasks.append(asyncio.create_task(single_request(session, url)))
        await asyncio.sleep(interval)

    if tasks:
        await asyncio.gather(*tasks)


async def replay_pattern(csv_path: str, url: str):
    """
    Replay a pattern CSV against the given URL.
    Each row is treated as one logical minute of wall-clock time.
    """
    async with aiohttp.ClientSession() as session:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                minute_str = row["minute"]  # for logging only
                rpm = float(row["invocations_per_minute"])
                print(f"Starting minute {minute_str} at rate {rpm} req/min")
                await fire_minute(session, url, rpm)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Replay minute-level workload pattern as HTTP load."
    )
    parser.add_argument(
        "csv_path",
        help="Path to pattern CSV (pattern_diurnal.csv, etc.)"
    )
    parser.add_argument(
        "url",
        help="Target service URL (e.g. http://light-api.default.127.0.0.1.sslip.io)"
    )
    args = parser.parse_args()

    asyncio.run(replay_pattern(args.csv_path, args.url))


if __name__ == "__main__":
    main()