import json
from datetime import datetime
from io import StringIO
from os import environ
import re
from time import monotonic, sleep

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Volume defined in compose.yaml
LLM_INPUT_DIRECTORY: str = "/llm_data/llm_inputs"


class Scraper:
    def __init__(self, request_delay: float = 4.0):
        self.last_request_time = 0.0
        self.request_delay = request_delay

    def get(self, url: str) -> requests.Response:
        if monotonic() - self.last_request_time < self.request_delay:
            sleep(self.request_delay - (monotonic() - self.last_request_time))
        r = requests.get(url)
        self.last_request_time = monotonic()
        return r


def get_urls() -> list[str]:
    r = requests.get("https://www.baseball-reference.com/boxes")
    b = BeautifulSoup(r.text, "lxml")
    return [
        "https://www.baseball-reference.com" + str(s.select("a")[1].get("href"))
        for s in b.select("div.game_summary")
    ]


def split_team_name(full: str) -> tuple[str, str]:
    return {
        "Baltimore Orioles": ("Baltimore", "Orioles"),
        "Boston Red Sox": ("Boston", "Red Sox"),
        "New York Yankees": ("New York", "Yankees"),
        "Tampa Bay Rays": ("Tampa Bay", "Rays"),
        "Toronto Blue Jays": ("Toronto", "Blue Jays"),
        "Chicago White Sox": ("Chicago", "White Sox"),
        "Cleveland Guardians": ("Cleveland", "Guardians"),
        "Detroit Tigers": ("Detroit", "Tigers"),
        "Kansas City Royals": ("Kansas City", "Royals"),
        "Minnesota Twins": ("Minnesota", "Twins"),
        "Houston Astros": ("Houston", "Astros"),
        "Los Angeles Angels": ("Los Angeles", "Angels"),
        "Oakland Athletics": ("Oakland", "Athletics"),
        "Seattle Mariners": ("Seattle", "Mariners"),
        "Texas Rangers": ("Texas", "Rangers"),
        "Atlanta Braves": ("Atlanta", "Braves"),
        "Miami Marlins": ("Miami", "Marlins"),
        "New York Mets": ("New York", "Mets"),
        "Philadelphia Phillies": ("Philadelphia", "Phillies"),
        "Washington Nationals": ("Washington", "Nationals"),
        "Chicago Cubs": ("Chicago", "Cubs"),
        "Cincinnati Reds": ("Cincinnati", "Reds"),
        "Milwaukee Brewers": ("Milwaukee", "Brewers"),
        "Pittsburgh Pirates": ("Pittsburgh", "Pirates"),
        "St. Louis Cardinals": ("St. Louis", "Cardinals"),
        "Arizona Diamondbacks": ("Arizona", "Diamondbacks"),
        "Colorado Rockies": ("Colorado", "Rockies"),
        "Los Angeles Dodgers": ("Los Angeles", "Dodgers"),
        "San Diego Padres": ("San Diego", "Padres"),
        "San Francisco Giants": ("San Francisco", "Giants"),
    }[full]


def extract_tables(c: str) -> list[list[str]]:
    cs = c.splitlines()
    ixs = [ix for ix, line in enumerate(cs) if "table_container" in line]
    tables: list[list[str]] = []
    for table_ix, line_ix in enumerate(ixs):
        tables.append([])
        while True:
            if "</table>" in cs[line_ix]:
                break
            elif cs[line_ix].strip() == "":
                pass
            else:
                tables[table_ix].append(cs[line_ix].strip())
            line_ix += 1
    return [t[1:] for t in tables]


def get_game_info(b) -> dict:
    pattern = re.compile("(World Series|ALWC|NLWC|ALCS|NLCS|ALDS|NLDS)")
    info = {}
    po_info = re.search(pattern, b.title.text)
    info["playoffs"] = po_info[0] if po_info is not None else ""
    info["playoff_series_status"] = ""

    info["game_date"] = b.title.text.split(": ")[1].split(" |")[0]

    scorebox = b.find("div", class_="scorebox")
    away = scorebox.find("div")
    info["away_team_name"] = away.find_all("a")[2].text
    info["away_standings"] = away.find_all("div")[4].text

    home = scorebox.find_all("div")[7]
    info["home_team_name"] = home.find_all("a")[2].text
    info["home_standings"] = home.find_all("div")[4].text
    return info


def parse_response(r: requests.Response) -> dict[str, str]:
    b = BeautifulSoup(r.content, "lxml")

    tables = extract_tables(str(r.text))

    data = []
    for t in tables:
        data.append(pd.read_html(StringIO("\n".join(t)))[0])

    away_batting = data[0].iloc[:, :-1].dropna()
    home_batting = data[1].iloc[:, :-1].dropna()
    away_pitching = data[2]
    away_pitching = away_pitching.drop(columns=["GSc", "IR", "IS"])
    home_pitching = data[3]
    home_pitching = home_pitching.drop(columns=["GSc", "IR", "IS"])
    big_plays = data[4]

    game_info = get_game_info(b)

    if game_info["playoffs"]:
        ps_summary_url = "https://www.baseball-reference.com" + b.find("div", class_="game_summaries").find_all("a")[-1].get("href")
        r = Scraper(4.0).get(ps_summary_url)
        bpo = BeautifulSoup(r.content)
        game_info["playoff_series_status"] = bpo.title.text.split(" - ")[1].split(" |")[0]

    boxscore = (
        pd.read_html(str(b.find("table", class_="linescore")), flavor="lxml")[0]
        .iloc[[0, 1], 1:]
        .rename(columns={"Unnamed: 1": "Team"})
    )

    away_team_city, away_team_name = split_team_name(game_info["away_team_name"])
    home_team_city, home_team_name = split_team_name(game_info["home_team_name"])

    if game_info["playoffs"]:
        series_history = game_info["playoff_series_status"].split()[-1]
        game_number = int(series_history[1]) + int(series_history[3])
        playoff_info = f'{game_info["playoffs"]} game {game_number}. {game_info["playoff_series_status"]}'
    else:
        playoff_info = ""

    game_date = datetime.strptime(game_info["game_date"], "%B %d, %Y").strftime("%Y-%m-%d")

    return {
        "date": game_date,
        "playoff_info": playoff_info,
        "away_team_city": away_team_city,
        "home_team_city": home_team_city,
        "away_team_name": away_team_name,
        "home_team_name": home_team_name,
        "away_standings": game_info["away_standings"],
        "home_standings": game_info["home_standings"],
        "boxscore": boxscore.to_csv(sep="|"),
        "away_batting": away_batting.to_csv(sep="|"),
        "home_batting": home_batting.to_csv(sep="|"),
        "away_pitching": away_pitching.to_csv(sep="|"),
        "home_pitching": home_pitching.to_csv(sep="|"),
        "big_plays": big_plays.to_csv(sep="|"),
    }


def save_data(data_dict: dict[str, str]):
    filename: str = f"{data_dict['date']}_{data_dict['home_team_name']}_at_{data_dict['away_team_name']}_{data_dict['game_number']}"

    with open(f"{LLM_INPUT_DIRECTORY}/{filename}.json", "w") as f:
        f.write(json.dumps(data_dict))


def main(limit: int | None = None):
    print("Starting pull-boxscores...")
    fn_start = monotonic()

    urls = get_urls()
    scraper = Scraper(4.0)

    print("Scraping site...")
    responses = []
    start = monotonic()
    for i, url in enumerate(urls[:limit]):
        print(f"{i + 1}/{len(urls)}")
        r = scraper.get(url)
        responses.append(r)
        print(f"Completed in {monotonic() - start:.1f}s")
        start = monotonic()

    print("Parsing site data...")
    seen_teams: list[str] = []  # Use to flag double-/triple-headers
    start = monotonic()
    for i, r in enumerate(responses):
        print(f"{i + 1}/{len(responses)}")

        data_dict = parse_response(r)
        data_dict["game_number"] = str(
            seen_teams.count(data_dict["home_team_name"]) + 1
        )
        seen_teams.append(data_dict["home_team_name"])
        save_data(data_dict)

        print(f"Completed in {monotonic() - start:.1f}s")
        start = monotonic()

    print(f"Finished pull-boxscores in {monotonic() - fn_start:.1f} s.")


if __name__ == "__main__":
    if environ["GS_TEST"] == "1":
        print("Detected test flag. Limiting number of pulls.")
        main(2)
    else:
        main()
